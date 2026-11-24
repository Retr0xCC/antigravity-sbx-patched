#!/usr/bin/env python3
"""
check_upstream.py - Checks whether the upstream SBX base image or QNIX patcher
has changed compared to the currently published downstream image in GHCR.

Writes key=value pairs to GITHUB_OUTPUT (when running in GitHub Actions):
  should_build=true|false
  upstream_digest=sha256:...
  patcher_sha=<40-char git sha>
  reason=<human-readable decision reason>
"""

import argparse
import base64
import hashlib
import json
import os
import re
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request


class _NoCrossHostAuthRedirectHandler(urllib.request.HTTPRedirectHandler):
    """Strips Authorization header when redirecting to a different host (e.g. CDN blobs)."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        redirected = super().redirect_request(req, fp, code, msg, headers, newurl)
        if redirected is None:
            return None
        src_host = urllib.parse.urlsplit(req.full_url).netloc
        dst_host = urllib.parse.urlsplit(redirected.full_url).netloc
        if src_host != dst_host:
            for key in list(redirected.headers.keys()):
                if key.lower() == "authorization":
                    redirected.remove_header(key)
        return redirected


_OPENER = urllib.request.build_opener(_NoCrossHostAuthRedirectHandler)


def parse_image_ref(ref: str) -> tuple[str, str, str]:
    """Parses an OCI image reference into (api_registry_host, repository, tag_or_digest)."""
    if "@" in ref:
        name_part, reference = ref.split("@", 1)
    else:
        last_slash = ref.rfind("/")
        last_colon = ref.rfind(":")
        if last_colon > last_slash:
            name_part, reference = ref[:last_colon], ref[last_colon + 1 :]
        else:
            name_part, reference = ref, "latest"

    parts = name_part.split("/", 1)
    if len(parts) == 2 and ("." in parts[0] or ":" in parts[0] or parts[0] == "localhost"):
        registry, repo = parts[0].lower(), parts[1].lower()
    else:
        registry = "docker.io"
        repo = name_part.lower()
        if "/" not in repo:
            repo = f"library/{repo}"

    api_host = "registry-1.docker.io" if registry == "docker.io" else registry
    return api_host, repo, reference


class RegistryReader:
    """Minimal read-only OCI Distribution v2 client using stdlib urllib."""

    def __init__(self, api_host: str, repo: str, username: str = None, token: str = None):
        self.api_host = api_host
        self.repo = repo
        self.base_url = f"https://{api_host}/v2/{repo}"
        self._basic_auth = self._resolve_basic_auth(api_host, username, token)
        self._bearer_token = None

    @staticmethod
    def _resolve_basic_auth(api_host: str, username: str = None, token: str = None) -> str | None:
        if api_host == "ghcr.io" and token:
            actor = username or "token"
            creds = base64.b64encode(f"{actor}:{token}".encode()).decode()
            return f"Basic {creds}"

        cfg_path = os.path.expanduser("~/.docker/config.json")
        if os.path.exists(cfg_path):
            try:
                with open(cfg_path, "r", encoding="utf-8") as f:
                    auths = json.load(f).get("auths", {})
                candidates = [api_host, f"https://{api_host}"]
                if api_host == "registry-1.docker.io":
                    candidates.extend(["https://index.docker.io/v1/", "docker.io", "https://docker.io"])
                for key in candidates:
                    entry = auths.get(key)
                    if isinstance(entry, dict) and entry.get("auth"):
                        return f"Basic {entry['auth']}"
            except Exception:
                pass
        return None

    def _fetch_bearer_token(self, www_auth: str):
        m_realm = re.search(r'realm="([^"]+)"', www_auth)
        if not m_realm:
            return
        realm = m_realm.group(1)
        m_service = re.search(r'service="([^"]+)"', www_auth)
        m_scope = re.search(r'scope="([^"]+)"', www_auth)

        params = {}
        if m_service:
            params["service"] = m_service.group(1)
        params["scope"] = m_scope.group(1) if m_scope else f"repository:{self.repo}:pull"
        token_url = f"{realm}?{urllib.parse.urlencode(params)}"

        req = urllib.request.Request(token_url)
        if self._basic_auth:
            req.add_header("Authorization", self._basic_auth)
        try:
            with _OPENER.open(req, timeout=30) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                self._bearer_token = data.get("token") or data.get("access_token")
        except urllib.error.HTTPError:
            if not self._basic_auth:
                raise
            # Fall back to anonymous token fetch for public repositories
            anon_req = urllib.request.Request(token_url)
            with _OPENER.open(anon_req, timeout=30) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                self._bearer_token = data.get("token") or data.get("access_token")

    def _get(self, url: str, headers: dict = None) -> tuple[bytes, dict]:
        req_headers = dict(headers or {})
        if self._bearer_token:
            req_headers["Authorization"] = f"Bearer {self._bearer_token}"

        req = urllib.request.Request(url, headers=req_headers, method="GET")
        try:
            with _OPENER.open(req, timeout=30) as resp:
                return resp.read(), dict(resp.headers.items())
        except urllib.error.HTTPError as e:
            www_auth = e.headers.get("Www-Authenticate", "")
            if e.code == 401 and www_auth:
                self._fetch_bearer_token(www_auth)
                if self._bearer_token:
                    req_headers["Authorization"] = f"Bearer {self._bearer_token}"
                retry_req = urllib.request.Request(url, headers=req_headers, method="GET")
                with _OPENER.open(retry_req, timeout=30) as resp:
                    return resp.read(), dict(resp.headers.items())
            raise

    def get_manifest(self, reference: str) -> tuple[dict, str]:
        accept = ", ".join([
            "application/vnd.oci.image.index.v1+json",
            "application/vnd.docker.distribution.manifest.list.v2+json",
            "application/vnd.oci.image.manifest.v1+json",
            "application/vnd.docker.distribution.manifest.v2+json",
        ])
        raw, resp_headers = self._get(f"{self.base_url}/manifests/{reference}", headers={"Accept": accept})
        digest = None
        for k, v in resp_headers.items():
            if k.lower() == "docker-content-digest":
                digest = v.strip()
                break
        if not digest:
            digest = f"sha256:{hashlib.sha256(raw).hexdigest()}"
        return json.loads(raw.decode("utf-8")), digest

    def resolve_amd64_manifest(self, reference: str) -> tuple[dict, str]:
        manifest, digest = self.get_manifest(reference)
        entries = manifest.get("manifests")
        if not isinstance(entries, list):
            return manifest, digest

        selected = None
        for entry in entries:
            annotations = entry.get("annotations") or {}
            if annotations.get("vnd.docker.reference.type") == "attestation-manifest":
                continue
            platform = entry.get("platform") or {}
            if platform.get("os") == "linux" and platform.get("architecture") == "amd64":
                selected = entry.get("digest")
                break
        if not selected:
            for entry in entries:
                annotations = entry.get("annotations") or {}
                if annotations.get("vnd.docker.reference.type") != "attestation-manifest" and entry.get("digest"):
                    selected = entry["digest"]
                    break
        if not selected:
            return manifest, digest
        return self.get_manifest(selected)

    def get_image_labels(self, reference: str) -> dict[str, str]:
        manifest, _ = self.resolve_amd64_manifest(reference)
        config_digest = (manifest.get("config") or {}).get("digest")
        if not config_digest:
            return {}
        raw_cfg, _ = self._get(f"{self.base_url}/blobs/{config_digest}")
        cfg = json.loads(raw_cfg.decode("utf-8"))
        return (cfg.get("config") or {}).get("Labels") or {}


def get_patcher_sha(repo_url: str, ref: str) -> str:
    """Resolves the remote commit SHA for the given patcher git ref."""
    for candidate in (f"refs/heads/{ref}", f"refs/tags/{ref}", ref):
        proc = subprocess.run(
            ["git", "ls-remote", repo_url, candidate],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if proc.returncode != 0:
            raise RuntimeError(f"git ls-remote failed ({proc.returncode}): {proc.stderr.strip()}")
        for line in proc.stdout.splitlines():
            parts = line.split()
            if parts and re.fullmatch(r"[0-9a-fA-F]{40}", parts[0]):
                return parts[0].lower()
    raise RuntimeError(f"Could not resolve ref '{ref}' in {repo_url}")


def write_github_output(path: str | None, values: dict[str, str]):
    if not path:
        return
    with open(path, "a", encoding="utf-8") as f:
        for key, val in values.items():
            f.write(f"{key}={val}\n")


def main():
    parser = argparse.ArgumentParser(description="Check upstream base image and patcher for updates")
    parser.add_argument("--base-image", default="docker.io/sbx/antigravity-image:latest")
    parser.add_argument("--target-image", default="ghcr.io/retr0xcc/antigravity-sbx-patched:latest")
    parser.add_argument("--patcher-repo", default="https://github.com/QNIX-Dev/eligibility-antigravity-patcher.git")
    parser.add_argument("--patcher-ref", default="main")
    parser.add_argument("--force", action="store_true", help="Always report should_build=true")
    parser.add_argument("--github-output", default=os.environ.get("GITHUB_OUTPUT"))
    args = parser.parse_args()

    upstream_digest = ""
    patcher_sha = ""
    try:
        up_host, up_repo, up_ref = parse_image_ref(args.base_image)
        up_client = RegistryReader(up_host, up_repo)
        _, upstream_digest = up_client.resolve_amd64_manifest(up_ref)
    except Exception as e:
        if not args.force:
            print(f"Error inspecting upstream base image '{args.base_image}': {e}", file=sys.stderr)
            sys.exit(1)
        print(f"Warning: could not inspect upstream base image '{args.base_image}': {e}", file=sys.stderr)

    try:
        patcher_sha = get_patcher_sha(args.patcher_repo, args.patcher_ref)
    except Exception as e:
        if not args.force:
            print(f"Error inspecting patcher repo '{args.patcher_repo}': {e}", file=sys.stderr)
            sys.exit(1)
        print(f"Warning: could not inspect patcher repo '{args.patcher_repo}': {e}", file=sys.stderr)

    published_digest = ""
    published_sha = ""
    target_missing = False

    if not args.force:
        try:
            tgt_host, tgt_repo, tgt_ref = parse_image_ref(args.target_image)
            tgt_client = RegistryReader(
                tgt_host,
                tgt_repo,
                username=os.environ.get("GITHUB_ACTOR"),
                token=os.environ.get("GITHUB_TOKEN") or os.environ.get("REGISTRY_TOKEN"),
            )
            labels = tgt_client.get_image_labels(tgt_ref)
            published_digest = labels.get("io.antigravity.upstream.digest", "")
            published_sha = labels.get("io.antigravity.patcher.sha", "")
        except urllib.error.HTTPError as e:
            if e.code == 404:
                target_missing = True
            else:
                print(f"Warning: could not inspect target image '{args.target_image}' (HTTP {e.code}); rebuilding.", file=sys.stderr)
                target_missing = True
        except Exception as e:
            print(f"Warning: could not inspect target image '{args.target_image}': {e}; rebuilding.", file=sys.stderr)
            target_missing = True

    if args.force:
        should_build = True
        reason = "forced build"
    elif target_missing:
        should_build = True
        reason = "target image not found or inaccessible"
    elif not published_digest or not published_sha:
        should_build = True
        reason = "published image lacks upstream tracking labels"
    elif upstream_digest != published_digest:
        should_build = True
        reason = f"upstream digest changed ({published_digest[:19]} -> {upstream_digest[:19]})"
    elif patcher_sha != published_sha:
        should_build = True
        reason = f"patcher commit changed ({published_sha[:12]} -> {patcher_sha[:12]})"
    else:
        should_build = False
        reason = "upstream image and patcher are up to date"

    print(f"Base image      : {args.base_image}")
    print(f"Upstream digest : {upstream_digest or '<unknown>'}")
    print(f"Patcher SHA     : {patcher_sha or '<unknown>'}")
    if not args.force:
        print(f"Published digest: {published_digest or '<none>'}")
        print(f"Published SHA   : {published_sha or '<none>'}")
    print(f"Should build    : {str(should_build).lower()} ({reason})")

    write_github_output(
        args.github_output,
        {
            "should_build": "true" if should_build else "false",
            "upstream_digest": upstream_digest,
            "patcher_sha": patcher_sha,
            "reason": reason,
        },
    )


if __name__ == "__main__":
    main()

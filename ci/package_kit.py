#!/usr/bin/env python3
"""
package_kit.py - Packages and publishes Antigravity SBX Kit as an OCI Artifact.

Creates an OCI artifact conforming to Docker Sandbox Kit v2:
  artifactType: application/vnd.docker.sandbox.kit.v2
  config.mediaType: application/vnd.docker.sandbox.kit.v2.spec+yaml

Ensures downstream compliance:
  - Verifies or injects downstream image reference (ghcr.io/retr0xcc/antigravity-sbx-patched)
  - Packages spec.yaml and AGENTS.md
  - Pushes directly to OCI registry (GHCR/Docker Hub) or exports OCI layout
"""

import argparse
import base64
import hashlib
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone


def compute_digest_and_size(data: bytes) -> tuple[str, int]:
    digest = f"sha256:{hashlib.sha256(data).hexdigest()}"
    return digest, len(data)


def parse_simple_yaml_fields(content: str) -> dict[str, str]:
    """Extracts top-level metadata fields from spec.yaml without requiring PyYAML."""
    fields = {}
    for line in content.splitlines():
        if line.startswith("#"):
            continue
        m = re.match(r"^([a-zA-Z0-9_-]+):\s*['\"]?(.*?)['\"]?\s*$", line)
        if m:
            key, val = m.group(1), m.group(2)
            if key not in fields:
                fields[key] = val
    return fields


class OciRegistryClient:
    def __init__(self, registry: str, repo: str, token: str = None, username: str = None, password: str = None):
        self.registry = registry
        self.repo = repo
        self.base_url = f"https://{registry}/v2/{repo}"
        self.username = username or os.environ.get("GITHUB_ACTOR")
        self.password = password or token or os.environ.get("GITHUB_TOKEN")
        self._bearer_token = None
        self._basic_auth = None
        self._init_auth()

    def _init_auth(self):
        # Prepare Basic Auth header for token exchange
        if self.username and self.password:
            creds = base64.b64encode(f"{self.username}:{self.password}".encode()).decode()
            self._basic_auth = f"Basic {creds}"
        elif self.password:
            # If only token is provided, use username or 'token'
            u = self.username or "token"
            creds = base64.b64encode(f"{u}:{self.password}".encode()).decode()
            self._basic_auth = f"Basic {creds}"
        else:
            # Try reading docker config
            cfg_path = os.path.expanduser("~/.docker/config.json")
            if os.path.exists(cfg_path):
                try:
                    with open(cfg_path, "r") as f:
                        cfg = json.load(f)
                    auths = cfg.get("auths", {})
                    for reg in [self.registry, f"https://{self.registry}", f"https://{self.registry}/v1/", f"https://{self.registry}/v2/"]:
                        if reg in auths and "auth" in auths[reg]:
                            self._basic_auth = f"Basic {auths[reg]['auth']}"
                            break
                except Exception:
                    pass

    def _ensure_bearer_token(self, scope: str = None):
        """Acquires a valid JWT Bearer token from the registry auth service."""
        if self._bearer_token:
            return

        scope = scope or f"repository:{self.repo}:pull,push"
        # 1. Probe the registry endpoint to discover realm and service
        probe_url = f"https://{self.registry}/v2/"
        realm = f"https://{self.registry}/token"
        service = self.registry

        try:
            req = urllib.request.Request(probe_url)
            urllib.request.urlopen(req)
        except urllib.error.HTTPError as e:
            www_auth = e.headers.get("Www-Authenticate", "")
            m_realm = re.search(r'realm="([^"]+)"', www_auth)
            m_service = re.search(r'service="([^"]+)"', www_auth)
            if m_realm:
                realm = m_realm.group(1)
            if m_service:
                service = m_service.group(1)

        # 2. Query token realm with Basic auth credentials
        params = {"service": service, "scope": scope}
        token_url = f"{realm}?{urllib.parse.urlencode(params)}"
        req = urllib.request.Request(token_url)
        if self._basic_auth:
            req.add_header("Authorization", self._basic_auth)

        try:
            with urllib.request.urlopen(req) as resp:
                data = json.loads(resp.read().decode())
                self._bearer_token = data.get("token") or data.get("access_token")
        except urllib.error.HTTPError as e:
            err_msg = e.read().decode("utf-8", errors="ignore")
            raise RuntimeError(f"Authentication failed with {self.registry} (HTTP {e.code}): {err_msg}")

    def _request(self, method: str, url: str, data: bytes = None, headers: dict = None) -> urllib.request.urlopen:
        self._ensure_bearer_token()
        headers = dict(headers or {})
        if self._bearer_token:
            headers["Authorization"] = f"Bearer {self._bearer_token}"

        req = urllib.request.Request(url, data=data, headers=headers, method=method)
        try:
            return urllib.request.urlopen(req)
        except urllib.error.HTTPError as e:
            if e.code == 401 and "Www-Authenticate" in e.headers:
                # Refresh token and retry once
                self._bearer_token = None
                self._ensure_bearer_token()
                if self._bearer_token:
                    headers["Authorization"] = f"Bearer {self._bearer_token}"
                retry_req = urllib.request.Request(url, data=data, headers=headers, method=method)
                return urllib.request.urlopen(retry_req)
            raise

    def blob_exists(self, digest: str) -> bool:
        url = f"{self.base_url}/blobs/{digest}"
        try:
            resp = self._request("HEAD", url)
            return resp.status in (200, 202)
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return False
            raise

    def upload_blob(self, data: bytes, digest: str):
        if self.blob_exists(digest):
            print(f"  [blob] {digest[:19]}... already exists in registry.")
            return

        print(f"  [blob] Uploading {digest[:19]}... ({len(data)} bytes)")
        init_url = f"{self.base_url}/blobs/uploads/"
        try:
            resp = self._request("POST", init_url)
            location = resp.headers.get("Location")
            if not location:
                raise RuntimeError("Registry did not return Location header for blob upload")

            # Upload URL can be relative or absolute
            if not location.startswith("http"):
                location = urllib.parse.urljoin(f"https://{self.registry}", location)

            delim = "&" if "?" in location else "?"
            put_url = f"{location}{delim}digest={digest}"
            headers = {"Content-Type": "application/octet-stream", "Content-Length": str(len(data))}
            self._request("PUT", put_url, data=data, headers=headers)
        except urllib.error.HTTPError as e:
            # Monolithic fallback
            try:
                put_url = f"{self.base_url}/blobs/uploads/?digest={digest}"
                headers = {"Content-Type": "application/octet-stream", "Content-Length": str(len(data))}
                self._request("POST", put_url, data=data, headers=headers)
            except Exception:
                raise RuntimeError(f"Failed to upload blob {digest}: HTTP {e.code} - {e.read().decode('utf-8', errors='ignore')}")

    def put_manifest(self, tag: str, manifest_bytes: bytes, media_type: str):
        print(f"  [manifest] Pushing manifest to tag '{tag}' ({len(manifest_bytes)} bytes)")
        url = f"{self.base_url}/manifests/{tag}"
        headers = {
            "Content-Type": media_type,
            "Content-Length": str(len(manifest_bytes))
        }
        resp = self._request("PUT", url, data=manifest_bytes, headers=headers)
        if resp.status not in (200, 201, 202):
            raise RuntimeError(f"Failed to push manifest: status {resp.status}")
        print(f"==> Successfully published kit artifact to https://{self.registry}/{self.repo}:{tag}")


def create_kit_artifact(spec_path: str, downstream_image: str = None) -> tuple[dict, bytes, bytes]:
    """Prepares the OCI Sandbox Kit v2 manifest and blob payloads."""
    with open(spec_path, "r", encoding="utf-8") as f:
        spec_content = f.read()

    # Downstream verification / injection:
    # Ensure downstream image is used in sandbox.image
    if downstream_image:
        spec_content = re.sub(
            r"(sandbox:\s*\n\s*image:\s*)[^\n]+",
            rf"\g<1>{downstream_image}",
            spec_content
        )
    elif "ghcr.io/retr0xcc/antigravity-sbx-patched" not in spec_content and "antigravity-sbx-patched" not in spec_content:
        sys.stderr.write("WARNING: spec.yaml does not appear to point to the downstream patched image!\n")

    spec_bytes = spec_content.encode("utf-8")
    spec_digest, spec_size = compute_digest_and_size(spec_bytes)

    # Empty layer required by OCI Image Spec
    empty_layer_bytes = b"{}"
    empty_digest, empty_size = compute_digest_and_size(empty_layer_bytes)

    meta = parse_simple_yaml_fields(spec_content)
    now_utc = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    manifest = {
        "schemaVersion": 2,
        "mediaType": "application/vnd.oci.image.manifest.v1+json",
        "artifactType": "application/vnd.docker.sandbox.kit.v2",
        "config": {
            "mediaType": "application/vnd.docker.sandbox.kit.v2.spec+yaml",
            "digest": spec_digest,
            "size": spec_size
        },
        "layers": [
            {
                "mediaType": "application/vnd.oci.empty.v1+json",
                "digest": empty_digest,
                "size": empty_size,
                "data": "e30="
            }
        ],
        "annotations": {
            "org.opencontainers.image.created": now_utc,
            "org.opencontainers.image.title": meta.get("displayName", "Google Antigravity (Patched)"),
            "org.opencontainers.image.description": meta.get("description", "Google's agent-first development platform, available as the agy terminal coding agent with QNIX eligibility patch pre-baked."),
            "vnd.docker.sandbox.kit.kind": meta.get("kind", "sandbox"),
            "vnd.docker.sandbox.kit.name": meta.get("name", "antigravity"),
            "vnd.docker.sandbox.kit.version": meta.get("version", "1.0.0")
        }
    }

    manifest_bytes = json.dumps(manifest, indent=2).encode("utf-8")
    return manifest, spec_bytes, manifest_bytes


def export_oci_layout(out_dir: str, manifest: dict, spec_bytes: bytes, manifest_bytes: bytes, tag: str = "latest"):
    os.makedirs(f"{out_dir}/blobs/sha256", exist_ok=True)
    with open(f"{out_dir}/oci-layout", "w") as f:
        json.dump({"imageLayoutVersion": "1.0.0"}, f)

    spec_digest = hashlib.sha256(spec_bytes).hexdigest()
    with open(f"{out_dir}/blobs/sha256/{spec_digest}", "wb") as f:
        f.write(spec_bytes)

    empty_bytes = b"{}"
    empty_digest = hashlib.sha256(empty_bytes).hexdigest()
    with open(f"{out_dir}/blobs/sha256/{empty_digest}", "wb") as f:
        f.write(empty_bytes)

    manifest_digest = hashlib.sha256(manifest_bytes).hexdigest()
    with open(f"{out_dir}/blobs/sha256/{manifest_digest}", "wb") as f:
        f.write(manifest_bytes)

    index = {
        "schemaVersion": 2,
        "manifests": [
            {
                "mediaType": "application/vnd.oci.image.manifest.v1+json",
                "digest": f"sha256:{manifest_digest}",
                "size": len(manifest_bytes),
                "annotations": {
                    "org.opencontainers.image.ref.name": tag
                }
            }
        ]
    }
    with open(f"{out_dir}/index.json", "w") as f:
        json.dump(index, f, indent=2)

    print(f"==> Exported OCI layout to {out_dir} with tag '{tag}'")


def main():
    parser = argparse.ArgumentParser(description="Package and publish Antigravity SBX Kit as an OCI artifact")
    parser.add_argument("--spec", default="kits/antigravity/spec.yaml", help="Path to spec.yaml")
    parser.add_argument("--downstream-image", default="ghcr.io/retr0xcc/antigravity-sbx-patched:latest",
                        help="Downstream container image reference to enforce")
    parser.add_argument("--target", default="ghcr.io/retr0xcc/antigravity-kit:latest",
                        help="Target OCI reference (e.g. ghcr.io/retr0xcc/antigravity-kit:latest)")
    parser.add_argument("--additional-tags", nargs="*", default=[],
                        help="Additional tags to publish (e.g. v1.0.0)")
    parser.add_argument("--fallback-repo",
                        help="Fallback repository target if separate package creation is denied (e.g. ghcr.io/owner/repo:kit)")
    parser.add_argument("--output-dir", help="Export to local OCI Image Layout directory")
    parser.add_argument("--push", action="store_true", help="Push to OCI registry")
    parser.add_argument("--username", default=os.environ.get("GITHUB_ACTOR"),
                        help="Registry username (defaults to GITHUB_ACTOR)")
    parser.add_argument("--token", default=os.environ.get("GITHUB_TOKEN") or os.environ.get("REGISTRY_TOKEN"),
                        help="Registry auth token (defaults to GITHUB_TOKEN or REGISTRY_TOKEN)")

    args = parser.parse_args()

    print(f"==> Packaging Antigravity Sandbox Kit from {args.spec}...")
    print(f"    Downstream base image: {args.downstream_image}")
    manifest, spec_bytes, manifest_bytes = create_kit_artifact(args.spec, args.downstream_image)

    # Parse target
    target_match = re.match(r"^([^/]+)/(.+?)(?::([^:]+))?$", args.target)
    if not target_match:
        sys.stderr.write(f"Error: Invalid target reference '{args.target}'\n")
        sys.exit(1)

    registry = target_match.group(1).lower()
    repo = target_match.group(2).lower()
    tag = (target_match.group(3) or "latest").lower()

    if args.output_dir:
        export_oci_layout(args.output_dir, manifest, spec_bytes, manifest_bytes, tag)

    if args.push:
        print(f"==> Publishing kit artifact to {registry}/{repo}:{tag}...")
        client = OciRegistryClient(registry, repo, username=args.username, token=args.token)

        # 1. Upload blobs
        empty_bytes = b"{}"
        empty_digest = f"sha256:{hashlib.sha256(empty_bytes).hexdigest()}"
        spec_digest = f"sha256:{hashlib.sha256(spec_bytes).hexdigest()}"

        try:
            client.upload_blob(empty_bytes, empty_digest)
            client.upload_blob(spec_bytes, spec_digest)

            # 2. Upload manifest for primary tag
            client.put_manifest(tag, manifest_bytes, "application/vnd.oci.image.manifest.v1+json")

            # 3. Upload for additional tags if requested
            for add_tag in args.additional_tags:
                client.put_manifest(add_tag.lower(), manifest_bytes, "application/vnd.oci.image.manifest.v1+json")
        except Exception as e:
            if args.fallback_repo:
                sys.stderr.write(f"\n[Warning] Publishing to {registry}/{repo} failed: {e}\n")
                sys.stderr.write(f"==> Retrying with repository-scoped fallback target: {args.fallback_repo}...\n")
                fb_match = re.match(r"^([^/]+)/(.+?)(?::([^:]+))?$", args.fallback_repo)
                if fb_match:
                    f_reg = fb_match.group(1).lower()
                    f_repo = fb_match.group(2).lower()
                    f_tag = (fb_match.group(3) or "kit").lower()
                    fb_client = OciRegistryClient(f_reg, f_repo, username=args.username, token=args.token)
                    fb_client.upload_blob(empty_bytes, empty_digest)
                    fb_client.upload_blob(spec_bytes, spec_digest)
                    fb_client.put_manifest(f_tag, manifest_bytes, "application/vnd.oci.image.manifest.v1+json")
                    return
            raise

    if not args.output_dir and not args.push:
        print("==> Dry run: Generated manifest:")
        print(json.dumps(manifest, indent=2))
        print("\nPass --push to publish to registry or --output-dir <path> to export local OCI layout.")


if __name__ == "__main__":
    main()

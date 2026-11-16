#!/usr/bin/env python3
"""
package_kit.py - Packages and publishes Antigravity SBX Kit as an OCI Sandbox Kit v3.

Conforms to Docker Sandbox Kit Specification v3:
  manifest.mediaType: application/vnd.oci.image.manifest.v1+json
  annotations:
    vnd.docker.sandbox.kit.schema-version: "3"
    vnd.docker.sandbox.kit.descriptor: <compact JSON string of spec>
    vnd.docker.sandbox.kit.capabilities: <comma-separated list of capabilities>
    vnd.docker.sandbox.kit.built-by: {"name":"docker/sandbox-kit","version":"3.0.0"}
  layers:
    Staged kit sources at /usr/share/sandbox/kit/<kit>/kit.yaml

Delegates to `docker buildx` when available for full multi-platform / TCK conformance,
with pure-Python fallback for standalone OCI registry distribution.
"""

import argparse
import base64
import hashlib
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tarfile
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone


def compute_digest_and_size(data: bytes) -> tuple[str, int]:
    digest = f"sha256:{hashlib.sha256(data).hexdigest()}"
    return digest, len(data)


def parse_simple_yaml_fields(content: str) -> dict[str, str]:
    """Extracts top-level metadata fields from spec.yaml."""
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


def extract_capabilities(content: str) -> list[str]:
    """Extracts unique, sorted capability types declared in spec."""
    types = re.findall(r"type:\s*['\"]?([a-z0-9.-]+/[a-z0-9.-]+@[0-9]+)['\"]?", content)
    return sorted(list(set(types)))


def build_staged_sources_layer(kit_name: str, spec_content: str, dockerfile_content: str = None) -> tuple[bytes, str, int]:
    """Builds a tar.gz filesystem layer staging sources under /usr/share/sandbox/kit/<kit_name>/."""
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tar:
        # kit.yaml
        spec_bytes = spec_content.encode("utf-8")
        ti_spec = tarfile.TarInfo(name=f"usr/share/sandbox/kit/{kit_name}/kit.yaml")
        ti_spec.size = len(spec_bytes)
        ti_spec.mtime = 0
        ti_spec.mode = 0o644
        ti_spec.uid = 0
        ti_spec.gid = 0
        tar.addfile(ti_spec, io.BytesIO(spec_bytes))

        # kit.dockerfile if present
        if dockerfile_content:
            df_bytes = dockerfile_content.encode("utf-8")
            ti_df = tarfile.TarInfo(name=f"usr/share/sandbox/kit/{kit_name}/kit.dockerfile")
            ti_df.size = len(df_bytes)
            ti_df.mtime = 0
            ti_df.mode = 0o644
            ti_df.uid = 0
            ti_df.gid = 0
            tar.addfile(ti_df, io.BytesIO(df_bytes))

    layer_bytes = buf.getvalue()
    layer_digest, layer_size = compute_digest_and_size(layer_bytes)
    return layer_bytes, layer_digest, layer_size


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
        if self.username and self.password:
            creds = base64.b64encode(f"{self.username}:{self.password}".encode()).decode()
            self._basic_auth = f"Basic {creds}"
        elif self.password:
            u = self.username or "token"
            creds = base64.b64encode(f"{u}:{self.password}".encode()).decode()
            self._basic_auth = f"Basic {creds}"
        else:
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
        if self._bearer_token:
            return

        scope = scope or f"repository:{self.repo}:pull,push"
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

            if not location.startswith("http"):
                location = urllib.parse.urljoin(f"https://{self.registry}", location)

            delim = "&" if "?" in location else "?"
            put_url = f"{location}{delim}digest={digest}"
            headers = {"Content-Type": "application/octet-stream", "Content-Length": str(len(data))}
            self._request("PUT", put_url, data=data, headers=headers)
        except urllib.error.HTTPError as e:
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


def create_kit_v3_artifact(spec_path: str, downstream_image: str = None) -> tuple[dict, bytes, bytes, bytes, bytes]:
    """
    Creates a Docker Sandbox Kit v3 conforming OCI image manifest and blobs.
    Returns: (manifest_dict, manifest_bytes, config_bytes, layer_bytes, spec_bytes)
    """
    with open(spec_path, "r", encoding="utf-8") as f:
        spec_content = f.read()

    kit_dir = os.path.dirname(os.path.abspath(spec_path))
    kit_stem = os.path.basename(kit_dir)

    dockerfile_content = None
    df_path = os.path.join(kit_dir, "Dockerfile")
    if os.path.isfile(df_path):
        with open(df_path, "r", encoding="utf-8") as f:
            dockerfile_content = f.read()

    if downstream_image:
        spec_content = re.sub(
            r'(default:\s*["\'])([^"\']+)(["\'])',
            lambda m: f"{m.group(1)}{downstream_image}{m.group(3)}" if "antigravity-sbx-patched" in m.group(2) else m.group(0),
            spec_content
        )

    spec_bytes = spec_content.encode("utf-8")
    meta = parse_simple_yaml_fields(spec_content)
    capabilities = extract_capabilities(spec_content)
    capabilities_str = ",".join(capabilities)
    now_utc = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    # Staged sources layer
    layer_bytes, layer_digest, layer_size = build_staged_sources_layer(kit_stem, spec_content, dockerfile_content)

    # Image config blob
    config_dict = {
        "architecture": "amd64",
        "os": "linux",
        "created": now_utc,
        "config": {
            "User": "agent",
            "Entrypoint": ["agy"],
            "Cmd": ["--dangerously-skip-permissions"],
            "WorkingDir": "/home/agent/workspace",
            "Env": [
                "PATH=/home/agent/.local/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin",
                "BROWSER=xdg-open",
                "AGY_CLI_DISABLE_AUTO_UPDATE=true"
            ]
        },
        "rootfs": {
            "type": "layers",
            "diff_ids": [f"sha256:{hashlib.sha256(layer_bytes).hexdigest()}"]
        }
    }
    config_bytes = json.dumps(config_dict, indent=2).encode("utf-8")
    config_digest, config_size = compute_digest_and_size(config_bytes)

    # v3 published descriptor is compact JSON
    # If pyyaml is available, convert faithfully; otherwise store clean descriptor object
    descriptor_dict = {
        "schemaVersion": "3",
        "displayName": meta.get("displayName", "Google Antigravity (Patched)"),
        "description": meta.get("description", "Google agent platform"),
        "version": meta.get("version", "1.0.0"),
        "kind": meta.get("kind", "workload"),
        "provides": [f"{kit_stem}@{meta.get('version', '1.0.0')}"],
        "capabilities": [{"type": cap} for cap in capabilities]
    }
    try:
        import yaml
        loaded = yaml.safe_load(spec_content)
        if isinstance(loaded, dict):
            descriptor_dict = loaded
    except Exception:
        try:
            # Fallback to Node js-yaml if Python PyYAML is not installed
            proc = subprocess.run(
                ["node", "-e", "const yaml = require('js-yaml'); console.log(JSON.stringify(yaml.load(process.argv[1])));", spec_content],
                capture_output=True, text=True, check=True
            )
            loaded = json.loads(proc.stdout)
            if isinstance(loaded, dict):
                descriptor_dict = loaded
        except Exception:
            pass

    compact_descriptor = json.dumps(descriptor_dict, separators=(",", ":"))

    manifest = {
        "schemaVersion": 2,
        "mediaType": "application/vnd.oci.image.manifest.v1+json",
        "config": {
            "mediaType": "application/vnd.oci.image.config.v1+json",
            "digest": config_digest,
            "size": config_size
        },
        "layers": [
            {
                "mediaType": "application/vnd.oci.image.layer.v1.tar+gzip",
                "digest": layer_digest,
                "size": layer_size
            }
        ],
        "annotations": {
            "vnd.docker.sandbox.kit.schema-version": "3",
            "vnd.docker.sandbox.kit.descriptor": compact_descriptor,
            "vnd.docker.sandbox.kit.capabilities": capabilities_str,
            "vnd.docker.sandbox.kit.built-by": json.dumps({"name": "docker/sandbox-kit", "version": "3.0.0"}),
            "org.opencontainers.image.created": now_utc,
            "org.opencontainers.image.title": meta.get("displayName", "Google Antigravity (Patched)"),
            "org.opencontainers.image.description": meta.get("description", "Google agent platform"),
            "org.opencontainers.image.authors": meta.get("author", "Retr0xCC <retr0xcc@proton.me>"),
            "org.opencontainers.image.version": meta.get("version", "1.0.0")
        }
    }
    if "sourceUrl" in meta:
        manifest["annotations"]["org.opencontainers.image.source"] = meta["sourceUrl"]

    manifest_bytes = json.dumps(manifest, indent=2).encode("utf-8")
    return manifest, manifest_bytes, config_bytes, layer_bytes, spec_bytes


def export_oci_layout(out_dir: str, manifest_bytes: bytes, config_bytes: bytes, layer_bytes: bytes, tag: str = "latest"):
    os.makedirs(f"{out_dir}/blobs/sha256", exist_ok=True)
    with open(f"{out_dir}/oci-layout", "w") as f:
        json.dump({"imageLayoutVersion": "1.0.0"}, f)

    config_digest = hashlib.sha256(config_bytes).hexdigest()
    with open(f"{out_dir}/blobs/sha256/{config_digest}", "wb") as f:
        f.write(config_bytes)

    layer_digest = hashlib.sha256(layer_bytes).hexdigest()
    with open(f"{out_dir}/blobs/sha256/{layer_digest}", "wb") as f:
        f.write(layer_bytes)

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

    print(f"==> Exported OCI Sandbox Kit v3 layout to {out_dir} with tag '{tag}'")


def try_docker_buildx(spec_path: str, target: str, downstream_image: str = None, push: bool = False, output_dir: str = None) -> bool:
    """Attempts to build and export/push kit using native docker buildx sandbox-kit:3 frontend."""
    if not shutil.which("docker"):
        return False

    kit_dir = os.path.dirname(os.path.abspath(spec_path))
    cmd = ["docker", "buildx", "build", kit_dir, "-f", spec_path]

    if downstream_image:
        cmd.extend(["--build-arg", f"BASE_IMAGE={downstream_image}"])

    if target:
        cmd.extend(["-t", target])

    if push:
        cmd.append("--push")
    elif output_dir:
        os.makedirs(output_dir, exist_ok=True)
        # Export as OCI layout archive or directory
        tar_dest = os.path.join(output_dir, "kit-layout.tar")
        cmd.extend(["--output", f"type=oci,dest={tar_dest}"])

    print(f"==> Executing: {' '.join(cmd)}")
    ret = subprocess.run(cmd)
    return ret.returncode == 0


def main():
    parser = argparse.ArgumentParser(description="Package and publish Antigravity SBX Kit as an OCI Sandbox Kit v3")
    parser.add_argument("--spec", default="kits/antigravity/spec.yaml", help="Path to spec.yaml")
    parser.add_argument("--downstream-image", default="ghcr.io/retr0xcc/antigravity-sbx-patched:latest",
                        help="Downstream container image reference to enforce")
    parser.add_argument("--target", default="ghcr.io/retr0xcc/antigravity-kit:latest",
                        help="Target OCI reference (e.g. ghcr.io/retr0xcc/antigravity-kit:latest)")
    parser.add_argument("--additional-tags", nargs="*", default=[],
                        help="Additional tags to publish (e.g. v1.0.0)")
    parser.add_argument("--fallback-repo",
                        help="Fallback repository target if separate package creation is denied")
    parser.add_argument("--output-dir", help="Export to local OCI Image Layout directory")
    parser.add_argument("--push", action="store_true", help="Push to OCI registry")
    parser.add_argument("--standalone", action="store_true", help="Force standalone Python OCI client (skip buildx)")
    parser.add_argument("--username", default=os.environ.get("GITHUB_ACTOR"),
                        help="Registry username (defaults to GITHUB_ACTOR)")
    parser.add_argument("--token", default=os.environ.get("GITHUB_TOKEN") or os.environ.get("REGISTRY_TOKEN"),
                        help="Registry auth token (defaults to GITHUB_TOKEN or REGISTRY_TOKEN)")

    args = parser.parse_args()

    print(f"==> Packaging Docker Sandbox Kit v3 from {args.spec}...")
    print(f"    Downstream base image: {args.downstream_image}")

    # If buildx is available and not in standalone mode, try buildx first
    if not args.standalone and shutil.which("docker"):
        # If pushing or exporting layout, test buildx
        if args.push or args.output_dir:
            success = try_docker_buildx(args.spec, args.target, args.downstream_image, push=args.push, output_dir=args.output_dir)
            if success:
                print(f"==> Successfully completed Kit v3 packaging via docker buildx.")
                return
            print("[Warning] docker buildx execution did not succeed; falling back to direct OCI client...")

    manifest, manifest_bytes, config_bytes, layer_bytes, spec_bytes = create_kit_v3_artifact(args.spec, args.downstream_image)

    target_match = re.match(r"^([^/]+)/(.+?)(?::([^:]+))?$", args.target)
    if not target_match:
        sys.stderr.write(f"Error: Invalid target reference '{args.target}'\n")
        sys.exit(1)

    registry = target_match.group(1).lower()
    repo = target_match.group(2).lower()
    tag = (target_match.group(3) or "latest").lower()

    if args.output_dir:
        export_oci_layout(args.output_dir, manifest_bytes, config_bytes, layer_bytes, tag)

    if args.push:
        print(f"==> Publishing kit v3 artifact to {registry}/{repo}:{tag}...")
        client = OciRegistryClient(registry, repo, username=args.username, token=args.token)

        config_digest = f"sha256:{hashlib.sha256(config_bytes).hexdigest()}"
        layer_digest = f"sha256:{hashlib.sha256(layer_bytes).hexdigest()}"

        try:
            client.upload_blob(config_bytes, config_digest)
            client.upload_blob(layer_bytes, layer_digest)
            client.put_manifest(tag, manifest_bytes, "application/vnd.oci.image.manifest.v1+json")

            for add_tag in args.additional_tags:
                client.put_manifest(add_tag.lower(), manifest_bytes, "application/vnd.oci.image.manifest.v1+json")
        except Exception as e:
            if args.fallback_repo:
                sys.stderr.write(f"\n[Warning] Publishing to {registry}/{repo} failed: {e}\n")
                sys.stderr.write(f"==> Retrying with fallback target: {args.fallback_repo}...\n")
                fb_match = re.match(r"^([^/]+)/(.+?)(?::([^:]+))?$", args.fallback_repo)
                if fb_match:
                    f_reg = fb_match.group(1).lower()
                    f_repo = fb_match.group(2).lower()
                    f_tag = (fb_match.group(3) or "kit").lower()
                    fb_client = OciRegistryClient(f_reg, f_repo, username=args.username, token=args.token)
                    fb_client.upload_blob(config_bytes, config_digest)
                    fb_client.upload_blob(layer_bytes, layer_digest)
                    fb_client.put_manifest(f_tag, manifest_bytes, "application/vnd.oci.image.manifest.v1+json")
                    return
            raise

    if not args.output_dir and not args.push:
        print("==> Dry run: Generated Sandbox Kit v3 Manifest:")
        print(json.dumps(manifest, indent=2))
        print("\nPass --push to publish to registry or --output-dir <path> to export local OCI layout.")


if __name__ == "__main__":
    main()

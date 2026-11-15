# Media Operator Kit (Docker Sandbox Mixin)

Autonomous media classification, metadata resolution, hardlink mapping, and AV1/HEVC transcoding plan generator for Jellyfin and Plex libraries.

## Architecture

This kit runs inside an isolated, read-only Docker Sandbox (SBX):
1. Raw media is mounted in **Read-Only (`:ro`)** at `/media/input`.
2. A dedicated output directory is mounted in **Read-Write (`:rw`)** at `/media/output`.
3. The AI agent inspects codecs via `ffprobe`, queries canonical metadata via allowed network endpoints, and writes:
   - `plan.json`: Structured execution manifest.
   - `summary.md`: Human-readable review report.
   - `apply.sh`: Standalone bash script.
4. Execution occurs natively on the host with native GPU acceleration and user permissions.

## Manual Launch Example

```bash
# Prepare output and host profile
mkdir -p ./out
cat <<EOF > ./out/host_profile.json
{
  "host_input_path": "/mnt/storage/Downloads/Torrents/AnimeSeries",
  "host_output_path": "/mnt/storage/Media/TV",
  "mode": "link",
  "gpu": {
    "backend": "vaapi",
    "codec": "av1",
    "encoder": "av1_vaapi",
    "device": "/dev/dri/renderD128"
  }
}
EOF

# Run sandbox planning
sbx run --template ghcr.io/retr0xcc/antigravity-sbx-patched:latest \
        --kit ./kits/media-operator \
        -v "/mnt/storage/Downloads/Torrents/AnimeSeries:/media/input:ro" \
        -v "$(pwd)/out:/media/output:rw"
```

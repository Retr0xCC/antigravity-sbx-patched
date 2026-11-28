#!/usr/bin/env bash
set -euo pipefail

# ========================================================
# Antigravity SBX Patched - Local Build Script
# Builds downstream from official Docker SBX upstream image
# ========================================================

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

BASE_IMAGE="${1:-docker.io/sbx/antigravity-image:latest}"
IMAGE_TAG="${2:-antigravity-sbx-patched:latest}"

echo "==> Building Antigravity SBX Patched image..."
echo "    Base image: ${BASE_IMAGE}"
echo "    Target tag: ${IMAGE_TAG}"

if command -v python3 >/dev/null 2>&1; then
    echo "==> Verifying kit prompt synchronization..."
    python3 "${SCRIPT_DIR}/sync_prompts.py" --check
fi

DOCKER_CMD="docker"
if ! command -v docker >/dev/null 2>&1; then
    if command -v podman >/dev/null 2>&1; then
        DOCKER_CMD="podman"
    else
        echo "Error: neither docker nor podman found in PATH." >&2
        exit 1
    fi
fi

"${DOCKER_CMD}" build \
    --build-arg BASE_IMAGE="${BASE_IMAGE}" \
    -t "${IMAGE_TAG}" \
    -f "${SCRIPT_DIR}/Dockerfile" \
    "${ROOT_DIR}"

echo "==> Validating built image..."
"${DOCKER_CMD}" run --rm "${IMAGE_TAG}" agy --version

echo "==> Building Media Operator image variant..."
MEDIA_TAG="${IMAGE_TAG%:latest}:media"
if [ "${MEDIA_TAG}" = "${IMAGE_TAG}" ]; then
    MEDIA_TAG="${IMAGE_TAG}-media"
fi
"${DOCKER_CMD}" build \
    --build-arg BASE_IMAGE="${IMAGE_TAG}" \
    -t "${MEDIA_TAG}" \
    -f "${ROOT_DIR}/kits/media-operator/Dockerfile" \
    "${ROOT_DIR}/kits/media-operator"

echo "==> Validating media tools in built media image..."
"${DOCKER_CMD}" run --rm "${MEDIA_TAG}" ffmpeg -version >/dev/null
"${DOCKER_CMD}" run --rm "${MEDIA_TAG}" mkvmerge --version >/dev/null
"${DOCKER_CMD}" run --rm "${MEDIA_TAG}" mediainfo --version >/dev/null
"${DOCKER_CMD}" run --rm "${MEDIA_TAG}" jq --version >/dev/null

echo "==> Building and tagging downstream Antigravity Sandbox Kit (v3)..."
"${DOCKER_CMD}" buildx build \
    "${ROOT_DIR}/kits/antigravity" \
    -f "${ROOT_DIR}/kits/antigravity/spec.yaml" \
    --build-arg BASE_IMAGE="${IMAGE_TAG}" \
    -t "ghcr.io/retr0xcc/antigravity-kit:latest"

echo "==> Packaging downstream Antigravity Sandbox Kit (OCI layout)..."
python3 "${SCRIPT_DIR}/package_kit.py" \
    --spec "${ROOT_DIR}/kits/antigravity/spec.yaml" \
    --downstream-image "${IMAGE_TAG}" \
    --output-dir "${ROOT_DIR}/dist/antigravity-kit"

echo "==> Building and tagging downstream Antigravity Local Sandbox Kit (v3)..."
"${DOCKER_CMD}" buildx build \
    "${ROOT_DIR}/kits/antigravity-local" \
    -f "${ROOT_DIR}/kits/antigravity-local/spec.yaml" \
    --build-arg BASE_IMAGE="${IMAGE_TAG}" \
    -t "ghcr.io/retr0xcc/antigravity-local-kit:latest"

echo "==> Packaging downstream Antigravity Local Sandbox Kit (OCI layout)..."
python3 "${SCRIPT_DIR}/package_kit.py" \
    --spec "${ROOT_DIR}/kits/antigravity-local/spec.yaml" \
    --downstream-image "${IMAGE_TAG}" \
    --target "ghcr.io/retr0xcc/antigravity-local-kit:latest" \
    --output-dir "${ROOT_DIR}/dist/antigravity-local-kit"

echo "==> Success! Images (${IMAGE_TAG}, ${MEDIA_TAG}) and kit artifacts are ready."
echo "    Usage with sbx (local kit):"
echo "      sbx run ./kits/antigravity"
echo "    Usage with sbx and mixin (local):"
echo "      sbx create --name my-sandbox ./kits/antigravity <workspace> --kit ./kits/affine-mcp"
echo "    Usage with sbx (published kit):"
echo "      sbx create --name my-sandbox \"ghcr.io/retr0xcc/antigravity-kit:latest\" <workspace> --kit ghcr.io/retr0xcc/affine-mcp-kit:latest"

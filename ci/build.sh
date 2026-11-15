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

echo "==> Packaging downstream Antigravity Sandbox Kit (OCI layout)..."
python3 "${SCRIPT_DIR}/package_kit.py" \
    --spec "${ROOT_DIR}/kits/antigravity/spec.yaml" \
    --downstream-image "${IMAGE_TAG}" \
    --output-dir "${ROOT_DIR}/dist/antigravity-kit"

echo "==> Success! Image ${IMAGE_TAG} and kit artifact are ready."
echo "    Usage with sbx (local kit):"
echo "      sbx run ./kits/antigravity --template ${IMAGE_TAG}"
echo "    Usage with sbx (published kit):"
echo "      sbx create --name my-sandbox \"ghcr.io/retr0xcc/antigravity-kit:latest\" <workspace> [mounts...]"

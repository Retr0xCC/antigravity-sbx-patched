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

echo "==> Success! Image ${IMAGE_TAG} is ready for use with sbx."
echo "    Usage with sbx:"
echo "      sbx run antigravity --template ${IMAGE_TAG}"

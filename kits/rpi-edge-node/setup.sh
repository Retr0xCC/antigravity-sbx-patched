#!/usr/bin/env bash
set -euo pipefail

# ========================================================
# RPi Edge Node Automation Kit Setup Hook
# ========================================================

echo "==> [sbx-kit:rpi-edge-node] Setting up Ansible toolchain and linters..."

if ! command -v uv >/dev/null 2>&1; then
    echo "Fatal: uv package manager not found. Please ensure uv is installed." >&2
    exit 1
fi

# Install Ansible toolchain via isolated uv tools
uv tool install ansible-core
uv tool install ansible-lint
uv tool install yamllint

# Install community.general collection
ansible-galaxy collection install community.general

echo "==> [sbx-kit:rpi-edge-node] Toolchain ready (Ansible, ansible-lint, yamllint)."

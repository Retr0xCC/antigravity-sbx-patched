#!/usr/bin/env bash
set -euo pipefail

# ========================================================
# Math Labs & Scientific Computing Kit Setup Hook
# ========================================================

KIT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_PATH="${HOME}/.venv"

echo "==> [sbx-kit:math-labs] Initializing Python scientific environment..."

if ! command -v uv >/dev/null 2>&1; then
    echo "Fatal: uv package manager not found. Please ensure uv is installed." >&2
    exit 1
fi

# Create dedicated virtualenv if not present
if [ ! -d "${VENV_PATH}" ]; then
    uv venv "${VENV_PATH}"
fi

# Install scientific packages
uv pip install --python "${VENV_PATH}/bin/python" -r "${KIT_DIR}/requirements.txt"

# Register Jupyter kernel
"${VENV_PATH}/bin/python" -m ipykernel install --user --name math-labs --display-name "Python (Math Labs)"

# Ensure virtual environment is active in persistent and interactive shells
if [ -w "/etc/sandbox-persistent.sh" ]; then
    if ! grep -q "${VENV_PATH}/bin" /etc/sandbox-persistent.sh 2>/dev/null; then
        echo "export PATH=\"${VENV_PATH}/bin:\$PATH\"" >> /etc/sandbox-persistent.sh
        echo "export VIRTUAL_ENV=\"${VENV_PATH}\"" >> /etc/sandbox-persistent.sh
    fi
fi
if ! grep -q "${VENV_PATH}/bin" "${HOME}/.bashrc" 2>/dev/null; then
    echo "export PATH=\"${VENV_PATH}/bin:\$PATH\"" >> "${HOME}/.bashrc"
    echo "export VIRTUAL_ENV=\"${VENV_PATH}\"" >> "${HOME}/.bashrc"
fi

echo "==> [sbx-kit:math-labs] Environment ready. Jupyter kernel 'math-labs' installed."

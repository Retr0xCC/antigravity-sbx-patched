#!/usr/bin/env bash
set -euo pipefail

# ========================================================
# AFFiNE MCP Workspace Kit Setup Hook
# ========================================================

echo "==> [sbx-kit:affine-mcp] Setting up AFFiNE MCP Server..."

# Install affine-mcp-server if binary is not present in PATH
if ! command -v affine-mcp >/dev/null 2>&1; then
    echo "==> Installing latest affine-mcp-server via npm..."
    npm install -g --ignore-scripts affine-mcp-server
fi

# Configure MCP server entry in ~/.gemini/config/mcp_config.json
MCP_CONFIG_DIR="${HOME}/.gemini/config"
MCP_CONFIG_FILE="${MCP_CONFIG_DIR}/mcp_config.json"
mkdir -p "${MCP_CONFIG_DIR}"
[ -s "${MCP_CONFIG_FILE}" ] || echo '{}' > "${MCP_CONFIG_FILE}"

if command -v jq >/dev/null 2>&1; then
    TMP_JSON="$(mktemp)"
    jq '.mcpServers.affine = {
        "command": "affine-mcp",
        "args": [],
        "env": {}
    }' "${MCP_CONFIG_FILE}" > "${TMP_JSON}" && mv "${TMP_JSON}" "${MCP_CONFIG_FILE}"
fi

echo "==> [sbx-kit:affine-mcp] AFFiNE MCP registered in ${MCP_CONFIG_FILE}."

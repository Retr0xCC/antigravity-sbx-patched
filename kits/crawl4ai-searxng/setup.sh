#!/usr/bin/env bash
set -euo pipefail

# ========================================================
# Crawl4AI & SearXNG Local MCP Kit Setup Hook
# ========================================================

echo "==> [sbx-kit:crawl4ai-searxng] Setting up local SearXNG & Crawl4AI MCP integration..."

strip_quotes() {
    local v="$1"
    v="${v#\"}" ; v="${v%\"}"
    v="${v#\'}" ; v="${v%\'}"
    printf '%s' "$v"
}

SEARXNG_MCP_URL="$(strip_quotes "${SEARXNG_MCP_URL:-http://host.docker.internal:3000/mcp}")"
CRAWL4AI_URL="$(strip_quotes "${CRAWL4AI_URL:-http://host.docker.internal:11235}")"
CRAWL4AI_URL="${CRAWL4AI_URL%/}"
TOKEN="$(strip_quotes "${CRAWL4AI_API_TOKEN:-${CRAWL4AI_SECRET_TOKEN:-}}")"

export PATH="${HOME}/.local/bin:${PATH}"

if ! command -v mcp-remote >/dev/null 2>&1; then
    echo "==> Installing mcp-remote bridge via npm..."
    npm install -g --ignore-scripts mcp-remote
fi

mkdir -p "${HOME}/.local/bin"
BRIDGE_BIN="${HOME}/.local/bin/crawl4ai-mcp-bridge"
cat > "${BRIDGE_BIN}" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
export PATH="$HOME/.local/bin:$HOME/.npm-global/bin:/usr/local/bin:$PATH"
URL="${CRAWL4AI_URL:-http://host.docker.internal:11235}"
URL="${URL#\"}" ; URL="${URL%\"}"
URL="${URL%/}"
TOKEN="${CRAWL4AI_API_TOKEN:-${CRAWL4AI_SECRET_TOKEN:-}}"
TOKEN="${TOKEN#\"}" ; TOKEN="${TOKEN%\"}"
ARGS=("${URL}/mcp/sse" --allow-http --transport sse-only)
if [ -n "${TOKEN}" ]; then
    ARGS+=(--header "Authorization: Bearer ${TOKEN}")
fi
exec mcp-remote "${ARGS[@]}"
EOF
chmod 0755 "${BRIDGE_BIN}"

if command -v jq >/dev/null 2>&1; then
    C4_ENV="$(jq -n --arg c4url "${CRAWL4AI_URL}" --arg token "${TOKEN}" \
        '{"CRAWL4AI_URL": $c4url} + (if $token != "" then {"CRAWL4AI_API_TOKEN": $token} else {} end)')"

    # 1. Google Antigravity
    GEMINI_CFG="${HOME}/.gemini/config/mcp_config.json"
    mkdir -p "$(dirname "${GEMINI_CFG}")"
    [ -s "${GEMINI_CFG}" ] || echo '{}' > "${GEMINI_CFG}"
    FRAG_GEMINI="$(mktemp)"
    jq -n --arg searx_url "${SEARXNG_MCP_URL}" --arg bridge "${BRIDGE_BIN}" --argjson env "${C4_ENV}" '{
        mcpServers: {
            searxng: {
                url: $searx_url
            },
            crawl4ai: {
                command: $bridge,
                args: [],
                env: $env
            }
        }
    }' > "${FRAG_GEMINI}"
    jq -s '.[0] * .[1]' "${GEMINI_CFG}" "${FRAG_GEMINI}" > "${GEMINI_CFG}.tmp" && mv "${GEMINI_CFG}.tmp" "${GEMINI_CFG}"
    rm -f "${FRAG_GEMINI}"

    # 2. OpenCode
    OPENCODE_CFG="${HOME}/.config/opencode/opencode.json"
    mkdir -p "$(dirname "${OPENCODE_CFG}")"
    [ -s "${OPENCODE_CFG}" ] || echo '{"$schema":"https://opencode.ai/config.json","mcp":{}}' > "${OPENCODE_CFG}"
    FRAG_OPENCODE="$(mktemp)"
    jq -n --arg searx_url "${SEARXNG_MCP_URL}" --arg bridge "${BRIDGE_BIN}" --argjson env "${C4_ENV}" '{
        mcp: {
            searxng: {
                type: "remote",
                url: $searx_url,
                enabled: true
            },
            crawl4ai: {
                type: "local",
                command: [$bridge],
                enabled: true,
                environment: $env
            }
        }
    }' > "${FRAG_OPENCODE}"
    jq -s '.[0] * .[1]' "${OPENCODE_CFG}" "${FRAG_OPENCODE}" > "${OPENCODE_CFG}.tmp" && mv "${OPENCODE_CFG}.tmp" "${OPENCODE_CFG}"
    rm -f "${FRAG_OPENCODE}"

    # 3. Claude Code
    CLAUDE_CFG="${HOME}/.claude.json"
    mkdir -p "$(dirname "${CLAUDE_CFG}")"
    [ -s "${CLAUDE_CFG}" ] || echo '{}' > "${CLAUDE_CFG}"
    FRAG_CLAUDE="$(mktemp)"
    jq -n --arg searx_url "${SEARXNG_MCP_URL}" --arg bridge "${BRIDGE_BIN}" --argjson env "${C4_ENV}" '{
        mcpServers: {
            searxng: {
                type: "http",
                url: $searx_url
            },
            crawl4ai: {
                command: $bridge,
                args: [],
                env: $env
            }
        }
    }' > "${FRAG_CLAUDE}"
    jq -s '.[0] * .[1]' "${CLAUDE_CFG}" "${FRAG_CLAUDE}" > "${CLAUDE_CFG}.tmp" && mv "${CLAUDE_CFG}.tmp" "${CLAUDE_CFG}"
    rm -f "${FRAG_CLAUDE}"
fi

echo "==> [sbx-kit:crawl4ai-searxng] Registered searxng (${SEARXNG_MCP_URL}) and crawl4ai (${CRAWL4AI_URL}/mcp/sse)."

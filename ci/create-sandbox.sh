#!/usr/bin/env bash
set -euo pipefail

# ==============================================================================
# Antigravity SBX - Kit Composition & Environment Launcher
#
# Creates an SBX sandbox using repo .env (automatically passed via --env-file),
# selects the appropriate Antigravity workload kit (antigravity or
# antigravity-local when local host kits like crawl4ai-searxng are attached),
# and composes one or more mixin kits.
# ==============================================================================

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

OWNER_REPO="${SBX_KIT_OWNER:-ghcr.io/retr0xcc}"
ENV_FILE="${ROOT_DIR}/.env"
SANDBOX_NAME=""
WORKSPACE_DIR=""
WORKLOAD=""
SOURCE_MODE="published"
AUTO_START="false"
DRY_RUN="false"
KITS=()
EXTRA_ARGS=()

usage() {
    cat <<EOF
Usage: $(basename "$0") [OPTIONS] [WORKSPACE_PATH]

Creates an SBX sandbox from kit compositions while automatically loading .env
from the repository root (${ROOT_DIR}/.env).

Options:
    --name <name>           Sandbox name (passed to sbx create --name)
    --workspace <path>      Target project workspace path (or pass as positional arg)
    --kit <name|ref>        Attach a mixin kit (repeatable). Short names like
                            'crawl4ai-searxng', 'affine-mcp', 'math-labs',
                            'rpi-edge-node', 'media-operator' resolve automatically.
    --workload <name|ref>   Workload kit (default: 'antigravity', or auto-switches
                            to 'antigravity-local' when 'crawl4ai-searxng' is used)
    --local                 Use local ./kits/<name> paths instead of GHCR images
    --published             Use published ${OWNER_REPO}/*-kit:latest images (default)
    --env-file <path>       Path to .env file (default: ${ROOT_DIR}/.env)
    --start                 Create and immediately attach using 'sbx run' instead of 'sbx create'
    --dry-run               Print the resolved sbx command without executing it
    -h, --help              Show this help message

Examples:
    # Create & start deep-research with local Crawl4AI + SearXNG using ./.env
    ./ci/create-sandbox.sh --name deep-research --kit crawl4ai-searxng /home/retro/Projects/deep-research --start

    # Create using local repo kits (no GHCR pull)
    ./ci/create-sandbox.sh --name deep-research --local --kit crawl4ai-searxng /home/retro/Projects/deep-research

    # Stack multiple mixin kits
    ./ci/create-sandbox.sh --name full --kit math-labs --kit affine-mcp /path/to/project
EOF
}

resolve_kit_ref() {
    local input="$1"
    if [[ "${input}" == ./* || "${input}" == /* || "${input}" == */* || "${input}" == *:* ]]; then
        echo "${input}"
        return
    fi
    if [[ "${SOURCE_MODE}" == "local" ]]; then
        echo "${ROOT_DIR}/kits/${input}"
    else
        echo "${OWNER_REPO}/${input}-kit:latest"
    fi
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --name)
            SANDBOX_NAME="${2:-}"
            shift 2
            ;;
        --workspace)
            WORKSPACE_DIR="${2:-}"
            shift 2
            ;;
        --kit)
            KITS+=("${2:-}")
            shift 2
            ;;
        --workload)
            WORKLOAD="${2:-}"
            shift 2
            ;;
        --local)
            SOURCE_MODE="local"
            shift
            ;;
        --published)
            SOURCE_MODE="published"
            shift
            ;;
        --env-file)
            ENV_FILE="${2:-}"
            shift 2
            ;;
        --start)
            AUTO_START="true"
            shift
            ;;
        --dry-run)
            DRY_RUN="true"
            shift
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        --)
            shift
            EXTRA_ARGS+=("$@")
            break
            ;;
        -*)
            EXTRA_ARGS+=("$1")
            shift
            ;;
        *)
            if [[ -z "${WORKSPACE_DIR}" ]]; then
                WORKSPACE_DIR="$1"
            else
                EXTRA_ARGS+=("$1")
            fi
            shift
            ;;
    esac
done

if [[ -z "${WORKSPACE_DIR}" ]]; then
    echo "Error: workspace path is required." >&2
    usage >&2
    exit 1
fi

# Auto-select antigravity-local when crawl4ai-searxng is requested unless overridden
if [[ -z "${WORKLOAD}" ]]; then
    WORKLOAD="antigravity"
    for k in ${KITS[@]+"${KITS[@]}"}; do
        if [[ "${k}" == *"crawl4ai-searxng"* ]]; then
            WORKLOAD="antigravity-local"
            break
        fi
    done
fi

WORKLOAD_REF="$(resolve_kit_ref "${WORKLOAD}")"

SUBCMD="create"
if [[ "${AUTO_START}" == "true" ]]; then
    SUBCMD="run"
fi

CMD=(sbx "${SUBCMD}")
if [[ -n "${SANDBOX_NAME}" ]]; then
    CMD+=(--name "${SANDBOX_NAME}")
fi

if [[ -f "${ENV_FILE}" ]]; then
    CMD+=(--env-file "${ENV_FILE}")
    # Also export GEMINI_API_KEY if non-empty in ENV_FILE so sbx credential prompt detects it
    gemini_val="$(grep -E '^GEMINI_API_KEY=' "${ENV_FILE}" | tail -n1 | cut -d= -f2- | sed -e 's/^["'\'']//' -e 's/["'\'']$//' || true)"
    if [[ -n "${gemini_val}" && -z "${GEMINI_API_KEY:-}" ]]; then
        export GEMINI_API_KEY="${gemini_val}"
    fi
else
    echo "Warning: env file '${ENV_FILE}' not found; creating sandbox without --env-file." >&2
fi

if [[ ${#EXTRA_ARGS[@]} -gt 0 ]]; then
    CMD+=("${EXTRA_ARGS[@]}")
fi
CMD+=("${WORKLOAD_REF}" "${WORKSPACE_DIR}")

for k in ${KITS[@]+"${KITS[@]}"}; do
    CMD+=(--kit "$(resolve_kit_ref "${k}")")
done

if [[ "${SOURCE_MODE}" == "local" ]] && command -v python3 >/dev/null 2>&1; then
    if ! python3 "${ROOT_DIR}/ci/sync_prompts.py" --check >/dev/null 2>&1; then
        echo "Warning: local kit prompts are out of sync with spec.yaml; run 'python3 ./ci/sync_prompts.py' before launching." >&2
    fi
fi

echo "==> Executing: ${CMD[*]}"
if [[ "${DRY_RUN}" == "true" ]]; then
    exit 0
fi

if ! command -v sbx >/dev/null 2>&1; then
    echo "Error: 'sbx' CLI is not found in PATH." >&2
    exit 1
fi

exec "${CMD[@]}"

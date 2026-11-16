#!/usr/bin/env bash
set -euo pipefail

# ==============================================================================
# Docker Sandboxes (SBX) - Native Network Policy Initializer
#
# Configures native Docker Sandboxes egress policy to grant full outbound
# Internet access (package managers, APIs, git, curl) while strictly denying
# access to the host machine, local LAN, private subnets (RFC 1918), and cloud
# instance metadata endpoints.
# ==============================================================================

RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

LOCAL_DENY_TARGETS="localhost,*.local,*.internal,*.lan,*.home.arpa,host.docker.internal,10.0.0.0/8,172.16.0.0/12,192.168.0.0/16,127.0.0.0/8,169.254.0.0/16"

usage() {
    cat <<EOF
Usage: $(basename "$0") [OPTIONS]

Configures Docker Sandboxes network policy with native Internet-only egress:
- Outbound Public Internet: ALLOWED (*)
- Host machine & LAN (RFC 1918): DENIED (10.0.0.0/8, 172.16.0.0/12, 192.168.0.0/16)
- Loopback & internal DNS: DENIED (127.0.0.0/8, localhost, *.local, *.internal, etc.)
- Cloud instance metadata: DENIED (169.254.0.0/16)

Options:
    --global              Apply network policy globally to all sandboxes (default)
    --sandbox <name>      Apply network policy scoped to a specific sandbox
    --check, --status     Inspect current network policies (sbx policy ls)
    --reset               Reset all custom policies (sbx policy reset)
    -h, --help            Show this help message

Examples:
    # Initialize global policy for all sandboxes
    ./ci/init-network.sh

    # Apply policy to a specific sandbox
    ./ci/init-network.sh --sandbox my-sandbox

    # Check active policies
    ./ci/init-network.sh --status
EOF
}

check_sbx() {
    if ! command -v sbx >/dev/null 2>&1; then
        echo -e "${RED}Error: 'sbx' CLI is not found in PATH.${NC}" >&2
        echo "Please install Docker Sandboxes CLI (sbx): https://docs.docker.com/ai/sandboxes/" >&2
        exit 1
    fi
}

SANDBOX_NAME=""
MODE="global"

while [[ $# -gt 0 ]]; do
    case "$1" in
        --global)
            MODE="global"
            shift
            ;;
        --sandbox)
            if [[ -z "${2:-}" ]]; then
                echo -e "${RED}Error: --sandbox requires a sandbox name argument.${NC}" >&2
                exit 1
            fi
            SANDBOX_NAME="$2"
            MODE="sandbox"
            shift 2
            ;;
        --check|--status)
            MODE="check"
            shift
            ;;
        --reset)
            MODE="reset"
            shift
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        *)
            echo -e "${RED}Unknown option: $1${NC}" >&2
            usage
            exit 1
            ;;
    esac
done

check_sbx

case "$MODE" in
    check)
        echo -e "${BLUE}==> Inspecting current Docker Sandboxes network policies...${NC}"
        sbx policy ls
        ;;
    reset)
        echo -e "${YELLOW}==> Resetting Docker Sandboxes network policies to defaults...${NC}"
        sbx policy reset
        echo -e "${GREEN}==> Network policies reset successfully.${NC}"
        ;;
    sandbox)
        echo -e "${BLUE}==> Configuring Internet-only network policy for sandbox '${SANDBOX_NAME}'...${NC}"
        echo "  [1/2] Allowing outbound public internet egress..."
        sbx policy allow network --sandbox "${SANDBOX_NAME}" "*"

        echo "  [2/2] Blocking local host, LAN subnets (RFC 1918), and cloud metadata..."
        sbx policy deny network --sandbox "${SANDBOX_NAME}" "${LOCAL_DENY_TARGETS}"

        echo -e "${GREEN}==> Successfully configured sandbox '${SANDBOX_NAME}' with Internet-only isolation.${NC}"
        ;;
    global)
        echo -e "${BLUE}==> Initializing global Docker Sandboxes network policy (allow-all)...${NC}"
        sbx policy init allow-all || {
            echo -e "${YELLOW}Note: 'sbx policy init' returned non-zero (policy may already be initialized). Continuing...${NC}"
        }

        echo -e "${BLUE}==> Applying global deny rules for local network & cloud metadata...${NC}"
        sbx policy deny network "${LOCAL_DENY_TARGETS}"

        echo -e "${GREEN}==> Successfully configured global Internet-only isolation for Docker Sandboxes.${NC}"
        echo "    Public Internet: ALLOWED (*)"
        echo "    Local LAN / Private IPs / Host / Metadata: BLOCKED"
        ;;
esac

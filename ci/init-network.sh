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
LOCAL_DENY_TARGETS_NO_HOST="localhost,*.local,*.lan,*.home.arpa,10.0.0.0/8,172.16.0.0/12,192.168.0.0/16,127.0.0.0/8,169.254.0.0/16"
HOST_SERVICES_ALLOW="host.docker.internal:3000,host.docker.internal:11235"

usage() {
    cat <<EOF
Usage: $(basename "$0") [OPTIONS]

Configures Docker Sandboxes network policy with native Internet-only egress:
- Outbound Public Internet: ALLOWED (*)
- Host machine & LAN (RFC 1918): DENIED (10.0.0.0/8, 172.16.0.0/12, 192.168.0.0/16)
- Loopback & internal DNS: DENIED (127.0.0.0/8, localhost, *.local, *.internal, etc.)
- Cloud instance metadata: DENIED (169.254.0.0/16)

Options:
    --global                Apply network policy globally to all sandboxes (default)
    --sandbox <name>        Apply network policy scoped to a specific sandbox
    --allow-host-services   Permit host.docker.internal (for local SearXNG MCP :3000 & Crawl4AI :11235)
                            while still blocking RFC 1918 LAN subnets, localhost, and metadata
    --check, --status       Inspect current network policies (sbx policy ls)
    --reset                 Reset all custom policies (sbx policy reset)
    -h, --help              Show this help message

Examples:
    # Initialize global policy for all sandboxes
    ./ci/init-network.sh

    # Initialize global policy allowing local host MCP services (SearXNG + Crawl4AI)
    ./ci/init-network.sh --allow-host-services

    # Apply policy to a specific sandbox
    ./ci/init-network.sh --sandbox my-sandbox --allow-host-services

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
ALLOW_HOST_SERVICES="false"

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
        --allow-host-services)
            ALLOW_HOST_SERVICES="true"
            shift
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

DENY_TARGETS="${LOCAL_DENY_TARGETS}"
if [[ "${ALLOW_HOST_SERVICES}" == "true" ]]; then
    DENY_TARGETS="${LOCAL_DENY_TARGETS_NO_HOST}"
fi

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

        if [[ "${ALLOW_HOST_SERVICES}" == "true" ]]; then
            echo "  [*] Removing global/sandbox deny on host.docker.internal & *.internal (if present) and allowing host services..."
            sbx policy rm network --sandbox "${SANDBOX_NAME}" --resource "host.docker.internal" >/dev/null 2>&1 || true
            sbx policy rm network --sandbox "${SANDBOX_NAME}" --resource "*.internal" >/dev/null 2>&1 || true
            sbx policy allow network --sandbox "${SANDBOX_NAME}" "${HOST_SERVICES_ALLOW}"
        fi

        echo "  [2/2] Blocking local host, LAN subnets (RFC 1918), and cloud metadata..."
        sbx policy deny network --sandbox "${SANDBOX_NAME}" "${DENY_TARGETS}"

        echo -e "${GREEN}==> Successfully configured sandbox '${SANDBOX_NAME}'.${NC}"
        ;;
    global)
        echo -e "${BLUE}==> Initializing global Docker Sandboxes network policy (allow-all)...${NC}"
        sbx policy init allow-all || {
            echo -e "${YELLOW}Note: 'sbx policy init' returned non-zero (policy may already be initialized). Continuing...${NC}"
        }

        if [[ "${ALLOW_HOST_SERVICES}" == "true" ]]; then
            echo -e "${BLUE}==> Removing existing deny rules for host.docker.internal & *.internal (if present)...${NC}"
            sbx policy rm network --resource "host.docker.internal" >/dev/null 2>&1 || true
            sbx policy rm network --resource "*.internal" >/dev/null 2>&1 || true
            sbx policy allow network "${HOST_SERVICES_ALLOW}"
        fi

        echo -e "${BLUE}==> Applying global deny rules for local network & cloud metadata...${NC}"
        sbx policy deny network "${DENY_TARGETS}"

        echo -e "${GREEN}==> Successfully configured global Docker Sandboxes network isolation.${NC}"
        echo "    Public Internet: ALLOWED (*)"
        if [[ "${ALLOW_HOST_SERVICES}" == "true" ]]; then
            echo "    Host Services (host.docker.internal): ALLOWED (${HOST_SERVICES_ALLOW})"
            echo "    Local LAN / Private IPs / Loopback / Metadata: BLOCKED"
        else
            echo "    Local LAN / Private IPs / Host / Metadata: BLOCKED"
        fi
        ;;
esac

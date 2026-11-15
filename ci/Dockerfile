# ========================================================
# Antigravity SBX Patched - Downstream Build
# Directly derives from official Docker SBX upstream image:
# docker.io/sbx/antigravity-image:latest
# In-place bleeding-edge QNIX eligibility patch & lockdown.
# ========================================================

ARG BASE_IMAGE=docker.io/sbx/antigravity-image:latest

FROM ${BASE_IMAGE}

ARG PATCHER_REPO=https://github.com/QNIX-Dev/eligibility-antigravity-patcher.git
ARG PATCHER_REF=main

USER root

# Apply QNIX eligibility patch in-place using bleeding-edge patcher
RUN set -eux; \
    rm -rf /tmp/patcher; \
    git clone --depth 1 --branch "${PATCHER_REF}" "${PATCHER_REPO}" /tmp/patcher; \
    \
    echo "==> Applying QNIX eligibility patch to /home/agent/.local/bin/agy..."; \
    python3 /tmp/patcher/manager.py patch cli --path-cli /home/agent/.local/bin/agy; \
    \
    echo "==> Verifying patch status..."; \
    STATUS_OUT="$(python3 /tmp/patcher/manager.py status cli --path-cli /home/agent/.local/bin/agy)"; \
    echo "${STATUS_OUT}"; \
    if ! echo "${STATUS_OUT}" | grep -qi "status: patched"; then \
        echo "FATAL: QNIX patch failed! Binary signature is unknown or unsupported by patcher." >&2; \
        exit 1; \
    fi; \
    \
    echo "==> Verifying patched binary execution..."; \
    /home/agent/.local/bin/agy --version; \
    \
    echo "==> Locking binary permissions (immutable for non-root agent)..."; \
    chmod 0555 /home/agent/.local/bin/agy; \
    rm -f /home/agent/.local/bin/agy.agybak; \
    \
    echo "==> Cleaning up patcher..."; \
    rm -rf /tmp/patcher /root/.cache

# Enforce disabling automatic updates so Google background updater never overwrites the patch
ENV AGY_CLI_DISABLE_AUTO_UPDATE=true
ENV PATH="/home/agent/.local/bin:${PATH}"

USER agent
WORKDIR /home/agent/workspace

ENTRYPOINT ["tini", "--"]
CMD ["agy", "--dangerously-skip-permissions"]

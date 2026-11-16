# syntax=docker/dockerfile:1
ARG BASE_IMAGE=ghcr.io/retr0xcc/antigravity-sbx-patched:latest
FROM ${BASE_IMAGE}

ENV BROWSER=xdg-open \
    AGY_CLI_DISABLE_AUTO_UPDATE=true

USER agent
WORKDIR /home/agent/workspace

ENTRYPOINT ["agy"]
CMD ["--dangerously-skip-permissions"]

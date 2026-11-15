# syntax=docker/dockerfile:1
ARG BASE_IMAGE=ghcr.io/retr0xcc/antigravity-sbx-patched:latest
FROM ${BASE_IMAGE}

USER root

# Pre-bake lightweight inspection and muxing tools (no GPU drivers needed in sandbox)
RUN set -eux; \
    apt-get update; \
    apt-get install -y --no-install-recommends \
        ffmpeg \
        mkvtoolnix \
        mediainfo \
        jq; \
    rm -rf /var/lib/apt/lists/*

USER agent
WORKDIR /home/agent/workspace

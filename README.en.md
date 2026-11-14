**English** | [Русский](README.ru.md)

# Antigravity SBX Patched

> Pre-built hardened **Google Antigravity** container with pre-integrated **QNIX** eligibility patch, built downstream from official `sbx/antigravity-image:latest`.

[![Docker Sandboxes](https://img.shields.io/badge/Docker%20Sandboxes-Supported-blue.svg)](https://docs.docker.com/)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Codeberg](https://img.shields.io/badge/Codeberg-Main_Repo-2185D0?logo=codeberg&logoColor=white)](https://codeberg.org/Retr0xCC/antigravity-sbx-patched)
[![GitHub](https://img.shields.io/badge/GitHub-Mirror-181717?logo=github&logoColor=white)](https://github.com/Retr0xCC/antigravity-sbx-patched)

---

## PART 1. Image and Build Guide

### 1.1. Key Highlights

* **Pre-Baked QNIX Patch**: Eligibility patch ([QNIX-Dev/eligibility-antigravity-patcher](https://github.com/QNIX-Dev/eligibility-antigravity-patcher)) is applied and verified at build time (`manager.py status cli -> status: patched`).
* **Auto-Update Lockdown**: The executable `/home/agent/.local/bin/agy` is made read-only (`chmod 0555`), and `AGY_CLI_DISABLE_AUTO_UPDATE=true` is enforced.

---

### 1.2. Quick Start

Images are published to **GitHub Packages (GHCR)** and **Codeberg**:

* `ghcr.io/Retr0xCC/antigravity-sbx-patched:latest`
* `codeberg.org/retr0xcc/antigravity-sbx-patched:latest`

#### Running in Docker Sandboxes (SBX)
```bash
sbx run antigravity --template ghcr.io/Retr0xCC/antigravity-sbx-patched:latest
```

#### Running in Standard Docker
```bash
docker run -it --rm \
  -v "$(pwd):/home/agent/workspace" \
  -w /home/agent/workspace \
  ghcr.io/Retr0xCC/antigravity-sbx-patched:latest bash
```

---

### 1.3. Building the Image Yourself

Downstream build directly from `sbx/antigravity-image:latest` with strict patch validation (build halts if the patch fails):

```bash
# Via build helper
./ci/build.sh

# Or direct docker build
docker build -t antigravity-sbx-patched:latest -f ci/Dockerfile .
```

* **GitHub Actions**: [.github/workflows/build-and-publish.yml](.github/workflows/build-and-publish.yml) builds and pushes to GHCR.
* **Codeberg Actions**: [.forgejo/workflows/build-and-publish.yml](.forgejo/workflows/build-and-publish.yml) builds and pushes to `codeberg.org`.

---

## PART 2. Templates and Kits (Optional)

```text
antigravity-sbx-patched/
├── templates/                   # Declarative workspace templates (sbxenv)
│   ├── sbxenv.yaml              # Universal starter template
│   ├── sbxenv-math.yaml         # Python, Jupyter, NumPy, SymPy, Pandas
│   ├── sbxenv-edge.yaml         # Ansible, Go, linters
│   ├── sbxenv-affine.yaml       # Node.js 22 LTS, AFFiNE MCP Server
│   └── .env.example             # Environment variable template
└── kits/                        # Modular SBX Kits (spec.yaml)
    ├── antigravity/             # Base Antigravity agent definition
    ├── math-labs/               # Scientific computing mixin
    ├── rpi-edge-node/           # Edge automation mixin
    └── affine-mcp/              # AFFiNE MCP server mixin
```

### 2.1. Declarative Workspace Setup (`sbxenv.yaml`)

```bash
# Copy template to project root
cp templates/sbxenv-math.yaml /path/to/my-project/sbxenv.yaml
cd /path/to/my-project

# Launch sandbox
sbx env run
```

### 2.2. Attaching Modular Kits Dynamically

```bash
# Attach specific toolchain
sbx run antigravity --kit ./kits/math-labs

# Stack multiple kits
sbx run antigravity --kit ./kits/math-labs --kit ./kits/affine-mcp
```

---

## License & Disclaimer

* This toolkit is open-sourced under the **[MIT License](LICENSE)** (© 2026 Retr0xCC).
* Eligibility patch logic is powered by [QNIX-Dev/eligibility-antigravity-patcher](https://github.com/QNIX-Dev/eligibility-antigravity-patcher) (MIT License, © 2026 QNIX-Dev).
* **Disclaimer**: This is an independent community project. It is not affiliated with, endorsed by, or sponsored by Google LLC or Docker, Inc. "Google Antigravity" is a trademark of Google LLC. "Docker" and "Docker Sandboxes" are trademarks of Docker, Inc.

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

Artifacts are automatically published to **GitHub Packages (GHCR)**:

* **Container Images**:
  - `ghcr.io/retr0xcc/antigravity-sbx-patched:latest` — minimal base image (agy + patch)
  - `ghcr.io/retr0xcc/antigravity-sbx-patched:media` — specialized media pipeline image (`ffmpeg`, `mkvtoolnix`, `mediainfo`, `jq`)
* **Sandbox Kit (OCI Artifact)**: `ghcr.io/retr0xcc/antigravity-kit:latest`

#### Running in Docker Sandboxes (SBX)

##### Option A. Via Published Kit (No Git clone needed)
The downstream kit is published to GHCR and references the patched `antigravity-sbx-patched` container image.

> **Important**: By default, Docker Sandboxes only permits installing kits from `docker.io/` and `dhi.io/`. To allow pulling kits from GHCR, run this once on your host:
> ```bash
> sbx settings set kit.allowedSources '["docker.io/","dhi.io/","ghcr.io/retr0xcc/"]'
> ```

```bash
# Create sandbox for project
sbx create --name my-sandbox "ghcr.io/retr0xcc/antigravity-kit:latest" /path/to/my-project

# Start and attach to the created sandbox
sbx start -a my-sandbox

# Or launch on the fly in the current directory:
sbx run "ghcr.io/retr0xcc/antigravity-kit:latest"
```

##### Option B. Via Local Kit from Repository
```bash
# Launch using defaults declared in spec.yaml
sbx run ./kits/antigravity

# Or create with custom workspace
sbx create --name my-sandbox "./kits/antigravity" /path/to/my-project
```

#### Running in Standard Docker
```bash
docker run -it --rm \
  -v "$(pwd):/home/agent/workspace" \
  -w /home/agent/workspace \
  ghcr.io/retr0xcc/antigravity-sbx-patched:latest bash
```

---

### 1.3. Building the Image Yourself

Downstream build directly from `sbx/antigravity-image:latest` with strict patch validation (build halts if the patch fails):

```bash
# Via build helper (builds base image and media variant)
./ci/build.sh

# Or direct docker build
docker build -t antigravity-sbx-patched:latest -f ci/Dockerfile .
docker build -t antigravity-sbx-patched:media -f kits/media-operator/Dockerfile kits/media-operator
```

* **GitHub Actions**: [.github/workflows/build-and-publish.yml](.github/workflows/build-and-publish.yml) builds and publishes the image to GHCR.

---

## PART 2. Templates

Two launch options are available:

1. **Kit** — Launch via `sbx run ./kits/antigravity` (or via published kit `ghcr.io/retr0xcc/antigravity-kit:latest`). Loads `kits/antigravity/spec.yaml`, providing:
   * Outbound network allowlist (Google OAuth, Generative Language API, Antigravity endpoints, GitHub).
   * Credentials injection (`GEMINI_API_KEY`) via secure proxyManaged with `x-goog-api-key` header injection.
   * Startup hooks (automatically generates `settings.json` and configures MCP Gateway).
   * Entrypoint: auto-launches `agy --dangerously-skip-permissions`.

2. **Env** — Launch via `sbx env run` using `sbxenv.yaml`. Uses built-in `agent: shell` with the container image. Ideal for an interactive shell with manual session management.

```text
antigravity-sbx-patched/
├── templates/                   # Declarative workspace templates (sbxenv)
│   ├── sbxenv.yaml              # Base template (agent: shell)
│   ├── sbxenv-math.yaml         # Python, Jupyter, NumPy, SymPy, Pandas
│   ├── sbxenv-edge.yaml         # Ansible, Go, linters
│   ├── sbxenv-affine.yaml       # Node.js 22 LTS, AFFiNE MCP Server
│   ├── sbxenv-media.yaml        # Media pipeline, Jellyfin/Plex planner
│   └── .env.example             # Environment variables (GEMINI_API_KEY)
└── kits/                        # Modular SBX Kits (spec.yaml)
    ├── antigravity/             # Base Antigravity agent definition (kind: sandbox)
    ├── math-labs/               # Scientific computing mixin (kind: mixin)
    ├── rpi-edge-node/           # Edge automation mixin (kind: mixin)
    ├── affine-mcp/              # AFFiNE MCP server mixin (kind: mixin)
    └── media-operator/          # Media pipeline & classifier mixin (kind: mixin)
```

### 2.1. Declarative Workspace Setup (`sbxenv.yaml`)

> [!WARNING]
> **Do not copy `sbxenv.yaml` into the root of `antigravity-sbx-patched`!**
> Placing `sbxenv.yaml` in the repository root litters the Git working tree and binds the SBX local state cache (`.sbx/`) to the toolkit source directory. Templates are meant to be copied to your separate project folders.

Templates declare `agent: shell` because `antigravity` is a modular kit rather than a built-in SBX system agent. Running `sbx env run` starts an interactive shell with the pre-installed and patched `agy` executable available.

```bash
# 1. Copy the template to your target project root
cp templates/sbxenv-math.yaml /path/to/my-project/sbxenv.yaml
cp templates/.env.example /path/to/my-project/.env
cd /path/to/my-project

# 2. Configure GEMINI_API_KEY in .env if needed

# 3. Launch sandbox (all container images and kits are pulled automatically from GHCR)
sbx env run
```

By default, templates reference published kits (`ghcr.io/retr0xcc/...-kit:latest`). If you want to use a local kit copy, specify the path:
```yaml
kits:
  - ./kits/math-labs
```

### 2.2. Attaching Kits Dynamically

When launching a sandbox, you can dynamically stack mixin kits using `--kit`:

```bash
# Launch shell agent with patched Antigravity and mixin kit
sbx run shell . --template ghcr.io/retr0xcc/antigravity-sbx-patched:latest \
  --kit ghcr.io/retr0xcc/math-labs-kit:latest

# Stack multiple kits
sbx run shell . --template ghcr.io/retr0xcc/antigravity-sbx-patched:latest \
  --kit ghcr.io/retr0xcc/math-labs-kit:latest \
  --kit ghcr.io/retr0xcc/affine-mcp-kit:latest
```

---

## License & Disclaimer

* This toolkit is open-sourced under the **[MIT License](LICENSE)** (© 2026 Retr0xCC).
* Eligibility patch logic is powered by [QNIX-Dev/eligibility-antigravity-patcher](https://github.com/QNIX-Dev/eligibility-antigravity-patcher) (MIT License, © 2026 QNIX-Dev).
* **Disclaimer**: This is an independent community project. It is not affiliated with, endorsed by, or sponsored by Google LLC or Docker, Inc. "Google Antigravity" is a trademark of Google LLC. "Docker" and "Docker Sandboxes" are trademarks of Docker, Inc.

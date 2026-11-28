# Crawl4AI & SearXNG Local MCP Kit

[English](#english) | [Русский](#русский)

---

<a name="english"></a>
## English

### Overview
This mixin Kit connects coding agents (**Antigravity**, **OpenCode**, **Claude Code**) inside an SBX sandbox to locally self-hosted **SearXNG MCP** (`isokoliuk/mcp-searxng`) and **Crawl4AI** (`unclecode/crawl4ai`) containers running on the host via `host.docker.internal`.

* **SearXNG MCP (`searxng`)**: Registered as a Streamable HTTP MCP server at `http://host.docker.internal:3000/mcp`.
* **Crawl4AI (`crawl4ai`)**: Registered via `~/.local/bin/crawl4ai-mcp-bridge` (`mcp-remote` stdio bridge) pointing to `http://host.docker.internal:11235/mcp/sse` with optional `Authorization: Bearer <CRAWL4AI_API_TOKEN>` authentication.

### 1. Expose Host Ports (Localhost-Only)
In your host `docker-compose.yml`, bind the container ports to `127.0.0.1` so the SBX host egress proxy (`host.docker.internal`) can reach them without exposing services to your LAN:

```yaml
  searxng-mcp:
    image: isokoliuk/mcp-searxng:latest
    ports:
      - "127.0.0.1:3000:3000"
    # ...

  crawl4ai:
    image: unclecode/crawl4ai:${CRAWL4AI_VERSION:-latest}
    ports:
      - "127.0.0.1:11235:11235"
    # ...
```

### 2. Allow Host Service Access in SBX Network Policy
> [!IMPORTANT]
> Docker Sandboxes enforces **Deny-First Precedence**. Because `kits/antigravity/spec.yaml` and the default `./ci/init-network.sh` explicitly deny `host.docker.internal` and `*.internal`, running `sbx run ./kits/antigravity --kit ./kits/crawl4ai-searxng` will block local host access unless those deny entries are removed.

To keep RFC 1918 LAN subnets, `localhost`, and cloud metadata blocked while allowing `host.docker.internal` ports `3000` and `11235`, initialize the host policy with:

```bash
./ci/init-network.sh --allow-host-services
```

Then launch your sandbox using `sbx env` or `shell` / `opencode`:

```bash
# Option A: Declarative workspace (Antigravity patched shell + Crawl4AI/SearXNG kit)
cp templates/sbxenv-crawl4ai-searxng.yaml /path/to/my-project/sbxenv.yaml
cp templates/.env.example /path/to/my-project/.env
# Set CRAWL4AI_API_TOKEN (if enabled on your Crawl4AI container) in .env
cd /path/to/my-project && sbx env run

# Option B: Direct shell or OpenCode launch
sbx run shell . --template ghcr.io/retr0xcc/antigravity-sbx-patched:latest --kit ./kits/crawl4ai-searxng
sbx run opencode . --kit ./kits/crawl4ai-searxng
```

### 3. Environment Variables & Verification
| Variable | Default | Description |
| :--- | :--- | :--- |
| `SEARXNG_MCP_URL` | `http://host.docker.internal:3000/mcp` | Streamable HTTP endpoint for `mcp-searxng` |
| `CRAWL4AI_URL` | `http://host.docker.internal:11235` | Base URL for Crawl4AI (`/mcp/sse`, `/crawl`, `/md`) |
| `CRAWL4AI_API_TOKEN` | `""` | Bearer token (`CRAWL4AI_SECRET_TOKEN` is also accepted as fallback) |

Verify connectivity from inside the sandbox:
```bash
curl -fsS http://host.docker.internal:3000/health
curl -fsS http://host.docker.internal:11235/health
curl -fsS http://host.docker.internal:11235/mcp/schema -H "Authorization: Bearer ${CRAWL4AI_API_TOKEN}"
```

---

<a name="русский"></a>
## Русский

### Обзор
Данный mixin-кит подключает агентов (**Antigravity**, **OpenCode**, **Claude Code**) внутри песочницы SBX к локально запущенным на хосте контейнерам **SearXNG MCP** (`isokoliuk/mcp-searxng`) и **Crawl4AI** (`unclecode/crawl4ai`) через `host.docker.internal`.

* **SearXNG MCP (`searxng`)**: Регистрируется как Streamable HTTP MCP-сервер по адресу `http://host.docker.internal:3000/mcp`.
* **Crawl4AI (`crawl4ai`)**: Регистрируется через локальный stdio-мост `~/.local/bin/crawl4ai-mcp-bridge` (на базе `mcp-remote`) к SSE-эндпоинту `http://host.docker.internal:11235/mcp/sse` с передачей `Authorization: Bearer <CRAWL4AI_API_TOKEN>` (если задан токен).

### 1. Публикация портов в `docker-compose.yml` (только localhost)
В вашем `docker-compose.yml` на хосте пробросьте порты строго на `127.0.0.1` — так прокси песочницы (`host.docker.internal`) сможет к ним обращаться, но сервисы останутся закрытыми для локальной сети:

```yaml
  searxng-mcp:
    image: isokoliuk/mcp-searxng:latest
    ports:
      - "127.0.0.1:3000:3000"
    # ...

  crawl4ai:
    image: unclecode/crawl4ai:${CRAWL4AI_VERSION:-latest}
    ports:
      - "127.0.0.1:11235:11235"
    # ...
```

### 2. Разрешение локального доступа к сервисам хоста в SBX
> [!IMPORTANT]
> В Docker Sandboxes действует модель **Deny-First Precedence** (запрет имеет приоритет над разрешением). Поскольку `kits/antigravity/spec.yaml` и базовый `./ci/init-network.sh` явно блокируют `host.docker.internal` и `*.internal`, при запуске `sbx run ./kits/antigravity --kit ./kits/crawl4ai-searxng` доступ к хосту будет заблокирован, пока эти правила запрета активны.

Чтобы оставить заблокированными LAN-подсети (RFC 1918), `localhost` и метаданные облака, но разрешить доступ к `host.docker.internal` (порты `3000` и `11235`), инициализируйте политику на хосте флагом `--allow-host-services`:

```bash
./ci/init-network.sh --allow-host-services
```

После этого запускайте песочницу через `sbx env` или `shell` / `opencode`:

```bash
# Вариант А: Декларативный шаблон (пропатченный agy + Crawl4AI/SearXNG кит)
cp templates/sbxenv-crawl4ai-searxng.yaml /path/to/my-project/sbxenv.yaml
cp templates/.env.example /path/to/my-project/.env
# Укажите CRAWL4AI_API_TOKEN (если включен на контейнере Crawl4AI) в .env
cd /path/to/my-project && sbx env run

# Вариант Б: Быстрый запуск через shell или OpenCode
sbx run shell . --template ghcr.io/retr0xcc/antigravity-sbx-patched:latest --kit ./kits/crawl4ai-searxng
sbx run opencode . --kit ./kits/crawl4ai-searxng
```

### 3. Переменные окружения и проверка
| Переменная | По умолчанию | Описание |
| :--- | :--- | :--- |
| `SEARXNG_MCP_URL` | `http://host.docker.internal:3000/mcp` | Streamable HTTP эндпоинт `mcp-searxng` |
| `CRAWL4AI_URL` | `http://host.docker.internal:11235` | Базовый URL Crawl4AI (`/mcp/sse`, `/crawl`, `/md`) |
| `CRAWL4AI_API_TOKEN` | `""` | Bearer-токен (также поддерживается `CRAWL4AI_SECRET_TOKEN`) |

Проверка связи изнутри песочницы:
```bash
curl -fsS http://host.docker.internal:3000/health
curl -fsS http://host.docker.internal:11235/health
curl -fsS http://host.docker.internal:11235/mcp/schema -H "Authorization: Bearer ${CRAWL4AI_API_TOKEN}"
```

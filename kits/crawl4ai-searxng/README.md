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

### 2. Launch with `antigravity-local` (or `sbxenv` / `opencode`)
> [!IMPORTANT]
> Docker Sandboxes enforces **Deny-First Precedence**. The default `antigravity` workload kit (`kits/antigravity`) explicitly denies `host.docker.internal` and `*.internal`, which blocks local host services.
> Use **`antigravity-local`** (`ghcr.io/retr0xcc/antigravity-local-kit:latest` or `./kits/antigravity-local`) instead: it keeps RFC 1918 LAN subnets, `localhost`, loopback, and cloud metadata blocked while omitting `"*"` and `host.docker.internal` from `deny`, so only the exact ports declared by `crawl4ai-searxng` (`3000`, `11235`) are opened.

```bash
# Option A (Recommended for Antigravity): Workload kit with local host service support
sbx run --name deep-research "ghcr.io/retr0xcc/antigravity-local-kit:latest" /path/to/my-project \
  --kit ghcr.io/retr0xcc/crawl4ai-searxng-kit:latest

# Or with local repository kits:
sbx run ./kits/antigravity-local --kit ./kits/crawl4ai-searxng

# Option B: Declarative workspace (Antigravity patched shell + Crawl4AI/SearXNG kit)
# (If you previously ran ./ci/init-network.sh without flags, re-run with --allow-host-services)
cp templates/sbxenv-crawl4ai-searxng.yaml /path/to/my-project/sbxenv.yaml
cp templates/.env.example /path/to/my-project/.env
# Set CRAWL4AI_API_TOKEN (if enabled on your Crawl4AI container) in .env
cd /path/to/my-project && sbx env run

# Option C: Direct shell or OpenCode launch
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

### 2. Запуск с `antigravity-local` (или `sbxenv` / `opencode`)
> [!IMPORTANT]
> В Docker Sandboxes действует модель **Deny-First Precedence** (запрет имеет приоритет над разрешением). Базовый workload-кит `antigravity` (`kits/antigravity`) жёстко блокирует `host.docker.internal` и `*.internal`.
> Для работы с локальными контейнерами используйте **`antigravity-local`** (`ghcr.io/retr0xcc/antigravity-local-kit:latest` или `./kits/antigravity-local`): он сохраняет блокировку LAN-подсетей (RFC 1918), `localhost`, loopback и метаданных облака, не включает `"*"` и не запрещает `host.docker.internal`, открывая только порты из `crawl4ai-searxng` (`3000`, `11235`).

```bash
# Вариант А (рекомендуется для Antigravity): Workload-кит с поддержкой локальных сервисов
sbx run --name deep-research "ghcr.io/retr0xcc/antigravity-local-kit:latest" /path/to/my-project \
  --kit ghcr.io/retr0xcc/crawl4ai-searxng-kit:latest

# Или через локальные киты из репозитория:
sbx run ./kits/antigravity-local --kit ./kits/crawl4ai-searxng

# Вариант Б: Декларативный шаблон (пропатченный agy + Crawl4AI/SearXNG кит)
# (Если ранее запускали ./ci/init-network.sh без флагов — выполните ./ci/init-network.sh --allow-host-services)
cp templates/sbxenv-crawl4ai-searxng.yaml /path/to/my-project/sbxenv.yaml
cp templates/.env.example /path/to/my-project/.env
# Укажите CRAWL4AI_API_TOKEN (если включен на контейнере Crawl4AI) в .env
cd /path/to/my-project && sbx env run

# Вариант В: Быстрый запуск через shell или OpenCode
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

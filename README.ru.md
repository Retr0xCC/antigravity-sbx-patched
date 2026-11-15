[English](README.en.md) | **Русский**

# Antigravity SBX Patched

> Готовый образ **Google Antigravity** с предварительно интегрированным eligibility-патчем **QNIX**, собранный на базе официального upstream-образа `sbx/antigravity-image:latest`.

[![Docker Sandboxes](https://img.shields.io/badge/Docker%20Sandboxes-Supported-blue.svg)](https://docs.docker.com/)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Codeberg](https://img.shields.io/badge/Codeberg-Main_Repo-2185D0?logo=codeberg&logoColor=white)](https://codeberg.org/Retr0xCC/antigravity-sbx-patched)
[![GitHub](https://img.shields.io/badge/GitHub-Mirror-181717?logo=github&logoColor=white)](https://github.com/Retr0xCC/antigravity-sbx-patched)

---

## ЧАСТЬ 1. Образ и сборка

### 1.1. Особенности образа

* **Встроенный QNIX Patch**: патч ([QNIX-Dev/eligibility-antigravity-patcher](https://github.com/QNIX-Dev/eligibility-antigravity-patcher)) применен и валидирован на этапе сборки (`manager.py status cli -> status: patched`).
* **Блокировка автообновлений**: бинарник `/home/agent/.local/bin/agy` зафиксирован (`chmod 0555`), установлена переменная `AGY_CLI_DISABLE_AUTO_UPDATE=true`.

---

### 1.2. Быстрый запуск

Артефакты автоматически публикуются в **GitHub Packages (GHCR)**:

* **Контейнерный образ**: `ghcr.io/retr0xcc/antigravity-sbx-patched:latest`
* **Sandbox Kit (OCI-артефакт)**: `ghcr.io/retr0xcc/antigravity-kit:latest`

#### В Docker Sandboxes (SBX)

##### Вариант А. Через опубликованный кит (без клонирования репозитория)
Downstream-кит опубликован в GHCR и автоматически ссылается на пропатченный образ `antigravity-sbx-patched`.

> **Важно**: По умолчанию Docker Sandboxes разрешает загрузку китов только из `docker.io/` и `dhi.io/`. Чтобы разрешить скачивание китов из GHCR, выполните на хосте один раз:
> ```bash
> sbx settings set kit.allowedSources '["docker.io/","dhi.io/","ghcr.io/retr0xcc/"]'
> ```

```bash
# Создание песочницы для проекта
sbx create --name my-sandbox "ghcr.io/retr0xcc/antigravity-kit:latest" /path/to/my-project

# Запуск созданной песочницы
sbx start -a my-sandbox

# Или быстрый запуск на лету в текущей папке:
sbx run "ghcr.io/retr0xcc/antigravity-kit:latest"
```

##### Вариант Б. Через локальный кит из репозитория
```bash
# Запуск с конфигурацией по умолчанию из spec.yaml
sbx run ./kits/antigravity

# Или создание песочницы с привязкой воркспейса
sbx create --name my-sandbox "./kits/antigravity" /path/to/my-project
```

#### В обычном Docker
```bash
docker run -it --rm \
  -v "$(pwd):/home/agent/workspace" \
  -w /home/agent/workspace \
  ghcr.io/retr0xcc/antigravity-sbx-patched:latest bash
```

---

### 1.3. Самостоятельная сборка

Сборка происходит downstream из `sbx/antigravity-image:latest` со строгой проверкой статуса патча (сборка завершится с ошибкой, если патч не применился):

```bash
# Через сборочный скрипт
./ci/build.sh

# Или напрямую через docker build
docker build -t antigravity-sbx-patched:latest -f ci/Dockerfile .
```

* **GitHub Actions**: [.github/workflows/build-and-publish.yml](.github/workflows/build-and-publish.yml) собирает образ и публикует его в GHCR.

---

## ЧАСТЬ 2. Шаблоны

Предусмотрено два варианта запуска:

1. **Kit** — запуск через `sbx run ./kits/antigravity` (или через опубликованный кит `ghcr.io/retr0xcc/antigravity-kit:latest`). Использует спецификацию `kits/antigravity/spec.yaml`, обеспечивая:
   * Сетевой allowlist (доступ к сервисам Google, OAuth, Generative Language API, Antigravity, GitHub).
   * Проброс учетных данных (`GEMINI_API_KEY`) через защищенный proxyManaged с инъекцией заголовка `x-goog-api-key`.
   * Startup-хуки (автоконфигурация `settings.json` и регистрация MCP Gateway).
   * Точку входа: запуск `agy --dangerously-skip-permissions`.

2. **Env** — запуск через `sbx env run` с использованием `sbxenv.yaml`. Использует встроенный агент `agent: shell` и образ контейнера. Подходит для интерактивной командной строки с ручным управлением сессией `agy`.

```text
antigravity-sbx-patched/
├── templates/                   # Декларативные шаблоны окружений (sbxenv)
│   ├── sbxenv.yaml              # Базовый шаблон (agent: shell)
│   ├── sbxenv-math.yaml         # Python, Jupyter, NumPy, SymPy, Pandas
│   ├── sbxenv-edge.yaml         # Ansible, Go, линтеры
│   ├── sbxenv-affine.yaml       # Node.js 22 LTS, AFFiNE MCP Server
│   └── .env.example             # Переменные окружения (GEMINI_API_KEY)
└── kits/                        # Модульные SBX Kits (spec.yaml)
    ├── antigravity/             # Базовый агент Antigravity (kind: sandbox)
    ├── math-labs/               # Научные вычисления (kind: mixin)
    ├── rpi-edge-node/           # Edge-автоматизация (kind: mixin)
    └── affine-mcp/              # MCP-сервер AFFiNE (kind: mixin)
```

### 2.1. Использование шаблонов (`sbxenv.yaml`)

> [!WARNING]
> **Не копируйте `sbxenv.yaml` в корень репозитория `antigravity-sbx-patched`!**
> Размещение `sbxenv.yaml` в корне репозитория засоряет рабочее дерево Git и привязывает состояние окружения SBX (`.sbx/`) к исходникам тулкита. Шаблоны предназначены для копирования в директории ваших целевых рабочих проектов.

Шаблоны используют `agent: shell`, поскольку `antigravity` является модульным китом, а не зарегистрированным системным агентом SBX. При запуске через `sbx env run` открывается интерактивная оболочка, в которой доступен пропатченный бинарник `agy`.

```bash
# 1. Скопируйте шаблон в корень вашего рабочего проекта
cp templates/sbxenv-math.yaml /path/to/my-project/sbxenv.yaml
cp templates/.env.example /path/to/my-project/.env
cd /path/to/my-project

# 2. Настройте GEMINI_API_KEY в файле .env (если требуется)

# 3. Запуск песочницы (все образы и киты автоматически подтягиваются из GHCR)
sbx env run
```

По умолчанию в шаблонах подключены опубликованные киты (`ghcr.io/retr0xcc/...-kit:latest`). При необходимости использовать локальную копию кита укажите путь:
```yaml
kits:
  - ./kits/math-labs
```

### 2.2. Подключение Kits на лету

При запуске песочницы можно на лету подключать mixin-киты с помощью флага `--kit`:

```bash
# Быстрый запуск агента shell с пропатченным Antigravity и mixin-китом
sbx run shell . --template ghcr.io/retr0xcc/antigravity-sbx-patched:latest \
  --kit ghcr.io/retr0xcc/math-labs-kit:latest

# Подключение нескольких наборов одновременно
sbx run shell . --template ghcr.io/retr0xcc/antigravity-sbx-patched:latest \
  --kit ghcr.io/retr0xcc/math-labs-kit:latest \
  --kit ghcr.io/retr0xcc/affine-mcp-kit:latest
```

---

## Лицензия и отказ от ответственности

* Исходный код этого тулкита распространяется под лицензией **[MIT](LICENSE)** (© 2026 Retr0xCC).
* Логика патчинга eligibility предоставлена проектом [QNIX-Dev/eligibility-antigravity-patcher](https://github.com/QNIX-Dev/eligibility-antigravity-patcher) (MIT License, © 2026 QNIX-Dev).
* **Disclaimer**: это независимый проект сообщества. Он не связан, не спонсируется и не одобрен компаниями Google LLC или Docker, Inc. «Google Antigravity» является товарным знаком Google LLC. «Docker» и «Docker Sandboxes» являются товарными знаками Docker, Inc.

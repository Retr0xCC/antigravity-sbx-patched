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

Образ доступен в **GitHub Packages (GHCR)** и **Codeberg**:

* `ghcr.io/Retr0xCC/antigravity-sbx-patched:latest`
* `codeberg.org/retr0xcc/antigravity-sbx-patched:latest`

#### В Docker Sandboxes (SBX)
```bash
sbx run antigravity --template ghcr.io/Retr0xCC/antigravity-sbx-patched:latest
```

#### В обычном Docker
```bash
docker run -it --rm \
  -v "$(pwd):/home/agent/workspace" \
  -w /home/agent/workspace \
  ghcr.io/Retr0xCC/antigravity-sbx-patched:latest bash
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

* **GitHub Actions**: [.github/workflows/build-and-publish.yml](.github/workflows/build-and-publish.yml) собирает и публикует образ в GHCR.
* **Codeberg Actions**: [.forgejo/workflows/build-and-publish.yml](.forgejo/workflows/build-and-publish.yml) публикует образ в `codeberg.org`.

---

## ЧАСТЬ 2. Шаблоны и Kits (Опционально)

```text
antigravity-sbx-patched/
├── templates/                   # Декларативные шаблоны окружений (sbxenv)
│   ├── sbxenv.yaml              # Базовый шаблон
│   ├── sbxenv-math.yaml         # Python, Jupyter, NumPy, SymPy, Pandas
│   ├── sbxenv-edge.yaml         # Ansible, Go, линтеры
│   ├── sbxenv-affine.yaml       # Node.js 22 LTS, AFFiNE MCP Server
│   └── .env.example             # Переменные окружения
└── kits/                        # Модульные SBX Kits (spec.yaml)
    ├── antigravity/             # Базовый агент Antigravity
    ├── math-labs/               # Научные вычисления
    ├── rpi-edge-node/           # Edge-автоматизация
    └── affine-mcp/              # MCP-сервер AFFiNE
```

### 2.1. Использование шаблонов (`sbxenv.yaml`)

```bash
# Скопируйте шаблон в корень вашего проекта
cp templates/sbxenv-math.yaml /path/to/my-project/sbxenv.yaml
cd /path/to/my-project

# Запуск песочницы
sbx env run
```

### 2.2. Подключение Kits на лету

```bash
# Подключение отдельного набора инструментов
sbx run antigravity --kit ./kits/math-labs

# Подключение нескольких наборов одновременно
sbx run antigravity --kit ./kits/math-labs --kit ./kits/affine-mcp
```

---

## Лицензия и отказ от ответственности

* Исходный код этого тулкита распространяется под лицензией **[MIT](LICENSE)** (© 2026 Retr0xCC).
* Логика патчинга eligibility предоставлена проектом [QNIX-Dev/eligibility-antigravity-patcher](https://github.com/QNIX-Dev/eligibility-antigravity-patcher) (MIT License, © 2026 QNIX-Dev).
* **Disclaimer**: это независимый проект сообщества. Он не связан, не спонсируется и не одобрен компаниями Google LLC или Docker, Inc. «Google Antigravity» является товарным знаком Google LLC. «Docker» и «Docker Sandboxes» являются товарными знаками Docker, Inc.

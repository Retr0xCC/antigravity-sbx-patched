# AFFiNE MCP Kit

[English](#english) | [Русский](#русский)

---

<a name="english"></a>
## English

### Overview
This Kit enables **Model Context Protocol (MCP)** integration between **Antigravity** and **AFFiNE Cloud** (`https://app.affine.pro`) or Self-Hosted instances.

### Quick Start

1. **Attach the Kit to an SBX sandbox:**
   ```bash
   sbx run ./kits/antigravity --kit ./kits/affine-mcp
   ```
   *(Or add `./kits/affine-mcp` to the `kits` section in your `sbxenv.yaml`)*

2. **Run the Setup Wizard:**
   Inside the container, launch the configuration wizard:
   ```bash
   ./kits/affine-mcp/affine-setup.sh
   ```
   * Paste your session `Cookie` header from `app.affine.pro` (F12 DevTools ➔ Network ➔ Request Headers ➔ `Cookie`).
   * Select your target workspace from the automatically discovered list.

3. **CLI Utilities:**
   * `./kits/affine-mcp/affine-setup.sh`: Interactive onboarding and configuration wizard.
   * `affine-mcp doctor`: Test API connection, GraphQL endpoint, and WebSocket.
   * `affine-mcp workspaces`: List accessible account workspaces.

---

<a name="русский"></a>
## Русский

### Обзор
Кит для интеграции **Antigravity** с **AFFiNE Cloud** (`https://app.affine.pro`) или внешними Self-Hosted серверами через протокол **Model Context Protocol (MCP)**.

### Быстрый старт

1. **Подключение кита в SBX:**
   ```bash
   sbx run ./kits/antigravity --kit ./kits/affine-mcp
   ```
   *(Или укажите `./kits/affine-mcp` в блоке `kits` вашего `sbxenv.yaml`)*

2. **Запуск мастера настройки:**
   Внутри запущенного контейнера выполните:
   ```bash
   ./kits/affine-mcp/affine-setup.sh
   ```
   * Вставьте значение заголовка `Cookie` из `app.affine.pro` (F12 DevTools ➔ вкладка Network ➔ заголовок `Cookie`).
   * Выберите нужный воркспейс из списка автоматически найденных.

3. **Команды управления:**
   * `./kits/affine-mcp/affine-setup.sh`: Интерактивный мастер авторизации и настройки.
   * `affine-mcp doctor`: Диагностика подключения к GraphQL и WebSocket.
   * `affine-mcp workspaces`: Список доступных рабочих пространств.

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

2. **Authenticate with AFFiNE:**
   Inside the container, run:
   ```bash
   affine-mcp login
   ```
   * Paste your session `Cookie` header from `app.affine.pro` (F12 DevTools ➔ Network ➔ Request Headers ➔ `Cookie`).
   * Select your target workspace from the automatically discovered list.

3. **CLI Utilities:**
   * `affine-mcp login`: Interactive authentication with AFFiNE Cloud or Self-Hosted instance.
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

2. **Авторизация в AFFiNE:**
   Внутри запущенного контейнера выполните:
   ```bash
   affine-mcp login
   ```
   * Вставьте значение заголовка `Cookie` из `app.affine.pro` (F12 DevTools ➔ вкладка Network ➔ заголовок `Cookie`).
   * Выберите нужный воркспейс из списка автоматически найденных.

3. **Команды управления:**
   * `affine-mcp login`: Интерактивная авторизация в AFFiNE Cloud или Self-Hosted сервере.
   * `affine-mcp doctor`: Диагностика подключения к GraphQL и WebSocket.
   * `affine-mcp workspaces`: Список доступных рабочих пространств.

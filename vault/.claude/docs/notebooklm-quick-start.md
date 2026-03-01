---
type: note
title: NotebookLM MCP CLI - Quick Start
last_accessed: 2026-02-26
relevance: 0.98
tier: active
---
# NotebookLM MCP CLI - Quick Start

> **Установлено:** 1 февраля 2026
> **Версия:** 0.2.10
> **GitHub:** https://github.com/jacob-bd/notebooklm-mcp-cli

---

## Зачем нужен NotebookLM

**Для обработки больших массивов данных:**
- Клиентские исследования и анализ
- Подготовка презентаций и брифингов
- Генерация подкастов из документации
- Создание обучающих материалов (флэшкарты, майндмэпы)
- Анализ конкурентов

---

## 🚀 Быстрый старт

### 1. Установка

```bash
uv tool install notebooklm-mcp-cli
```

**Установлены компоненты:**
- `nlm` — CLI команда
- `notebooklm-mcp` — MCP сервер (уже в конфиге)
- `notebooklm-mcp-auth` — аутентификация

### 2. Аутентификация

```bash
notebooklm-mcp-auth --file
```

**Инструкция:**
1. Открой Chrome → https://notebooklm.google.com
2. Открой DevTools (Cmd+Option+I)
3. Вкладка **Network** → фильтр: `batchexecute`
4. Кликни на любой ноутбук (появится запрос)
5. Найди **Request Headers** → строку `cookie:`
6. Скопируй значение (правый клик → Copy value)
7. Создай файл `~/cookies.txt` и вставь туда
8. Запусти: `notebooklm-mcp-auth --file ~/cookies.txt`

**Проверка:**
```bash
nlm list notebook
```

---

## 📚 Основные команды

### Управление ноутбуками

```bash
# Список всех ноутбуков
nlm list notebook

# Создать ноутбук
nlm create notebook "Название"

# Детали ноутбука
nlm get notebook "Название"

# Удалить ноутбук
nlm delete notebook "Название"

# Переименовать
nlm rename notebook "Старое" --new-name "Новое"
```

### Добавление источников

```bash
# URL
nlm add source --url https://example.com --notebook "My Research"

# YouTube видео
nlm add source --youtube https://youtube.com/watch?v=VIDEO_ID --notebook "My Research"

# Текст
nlm add source --text "Ваш текст здесь" --notebook "My Research"

# Google Drive файл
nlm add source --drive-file "FILE_ID" --notebook "My Research"

# Список источников
nlm list source --notebook "My Research"
```

### Запросы и анализ

```bash
# Задать вопрос к ноутбуку
nlm query "В чём основные инсайты?" --notebook "My Research"

# Получить описание
nlm describe notebook "My Research"

# Получить raw контент из источника
nlm content source "SOURCE_ID"
```

### Генерация контента

```bash
# Audio overview (подкаст)
nlm audio create --notebook "My Research"

# Video overview
nlm video create --notebook "My Research"

# Slides (презентация)
nlm slides create --notebook "My Research"

# Mind map
nlm mindmap create --notebook "My Research"

# Infographic
nlm infographic create --notebook "My Research"

# Flashcards
nlm flashcards create --notebook "My Research"

# Briefing document
nlm report create --notebook "My Research"

# Quiz
nlm quiz create --notebook "My Research"
```

### Синхронизация

```bash
# Синхронизировать Google Drive источники
nlm sync --notebook "My Research"

# Список устаревших источников
nlm stale --notebook "My Research"
```

### Шеринг

```bash
# Сделать ноутбук публичным
nlm share notebook "My Research" --public

# Поделиться с конкретным пользователем
nlm share notebook "My Research" --email user@example.com
```

---

## 🔧 Использование через MCP

### Через mcp-cli (рекомендуется)

```bash
# Список инструментов
mcp-cli info notebooklm

# Создать ноутбук
mcp-cli call notebooklm create_notebook '{"title": "Research"}'

# Добавить источник
mcp-cli call notebooklm add_source '{
  "notebook_id": "...",
  "url": "https://example.com"
}'

# Запрос
mcp-cli call notebooklm query '{
  "notebook_id": "...",
  "query": "What are the main points?"
}'

# Генерация подкаста
mcp-cli call notebooklm create_audio '{
  "notebook_id": "..."
}'
```

### Из Claude Code

```markdown
Используй NotebookLM для анализа этих статей:
- https://example.com/article1
- https://example.com/article2

Создай ноутбук "Competitor Analysis" и сгенерируй:
1. Briefing document
2. Mind map
3. Audio overview (подкаст)
```

---

## 💡 Use Cases

### 1. Client Research

```bash
nlm create notebook "Client Research: Acme Campaign"
nlm add source --url https://competitor1.com --notebook "Client Research: Acme Campaign"
nlm add source --url https://competitor2.com --notebook "Client Research: Acme Campaign"
nlm query "What patterns in mechanics?" --notebook "Client Research: Acme Campaign"
nlm slides create --notebook "Client Research: Acme Campaign"
nlm report create --notebook "Client Research: Acme Campaign"
```

### 2. Training Materials

```bash
nlm create notebook "AI Training Materials"
nlm add source --url https://docs.anthropic.com --notebook "AI Training Materials"
nlm add source --youtube https://youtube.com/watch?v=... --notebook "AI Training Materials"
nlm flashcards create --notebook "AI Training Materials"
nlm mindmap create --notebook "AI Training Materials"
nlm quiz create --notebook "AI Training Materials"
```

### 3. Content Generation

```bash
nlm create notebook "Content Ideas"
nlm add source --url https://research-article.com --notebook "Content Ideas"
nlm audio create --notebook "Content Ideas"  # Podcast
nlm infographic create --notebook "Content Ideas"  # Infographic
```

---

## ⚠️ Важно

- **Cookie-based auth** — токены хранятся локально, обновляются автоматически
- **Undocumented API** — может сломаться после обновлений Google
- **Personal use** — не для продакшена, только эксперименты
- **Rate limits** — Google может ограничить при частых запросах

---

## 📝 Профили

Если нужно несколько Google аккаунтов:

```bash
# Аутентификация с профилем
nlm login --profile work
nlm login --profile personal

# Переключение
nlm login switch work

# Список профилей
nlm login profile list

# Использование конкретного профиля
nlm list notebook --profile work
```

---

## 🔗 Ссылки

- **GitHub:** https://github.com/jacob-bd/notebooklm-mcp-cli
- **MEMORY.md:** `vault/MEMORY.md` — секция "NotebookLM"
- **MCP Config:** `~/.config/mcp/mcp_servers.json`

---

*Created: 2026-02-01*

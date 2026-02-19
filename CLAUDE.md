# Life Pilot Agent

Персональный AI-ассистент для захвата мыслей, голосовых заметок и управления задачами через Telegram. Интегрируется с Claude AI, Obsidian (хранение заметок) и Todoist (задачи). Целевая аудитория — один пользователь (владелец).

## Стек

- **Язык:** Python 3.12+
- **Менеджер пакетов:** uv (astral.sh)
- **Фреймворк:** aiogram 3.0+ (async Telegram bot)
- **Конфигурация:** pydantic 2.0+ / pydantic-settings (.env)
- **Транскрипция:** Deepgram SDK (модель nova-3, русский)
- **Задачи:** todoist-api-python 3.1.0+
- **HTTP:** httpx (async)
- **AI:** Claude Code CLI (вызов через subprocess)
- **MCP-серверы:** Todoist (`@doist/todoist-ai`), Google Calendar (`@modelcontextprotocol/server-google-calendar`)
- **Хранение:** файловая система (Obsidian vault, markdown + JSONL сессии)
- **Деплой:** systemd на Ubuntu VPS

## Архитектура

```
src/d_brain/
├── __main__.py              # Точка входа
├── config.py                # Pydantic Settings из .env
├── bot/
│   ├── main.py              # Инициализация бота, регистрация роутеров
│   ├── keyboards.py         # Reply-клавиатура (5 кнопок)
│   ├── formatters.py        # HTML-форматирование отчётов
│   ├── states.py            # FSM-состояния (DoCommand, Process, Monthly, Grow, Reflection, Recall)
│   ├── utils.py             # download_telegram_file, transcribe_voice, send_formatted_report
│   ├── progress.py          # run_with_progress() — async wrapper
│   ├── components/
│   │   └── task_keyboard.py # Reusable per-task inline keyboard (move/delete/done/skip)
│   └── handlers/            # Хендлеры по типу сообщений
│       ├── commands.py      # /start, /help, /status, /plan
│       ├── process.py       # /process — запуск Claude-обработки + clarification FSM
│       ├── do.py            # /do — произвольный запрос к Claude
│       ├── weekly.py        # /weekly — недельный дайджест
│       ├── weekly_callbacks.py  # Кнопки недельного отчёта + GROW trigger
│       ├── monthly.py       # /monthly + scheduled_monthly_report/reminder
│       ├── monthly_callbacks.py # Кнопки месячного отчёта + reformulation FSM
│       ├── grow.py          # GROW coaching FSM (answering/confirming/correcting)
│       ├── grow_scheduler.py # Scheduled GROW triggers (weekly/monthly/quarterly/yearly)
│       ├── reflection.py    # Legacy Friday reflection (сохранён для обратной совместимости)
│       ├── recall.py        # /recall — поиск по vault
│       ├── voice.py         # Голосовые сообщения → транскрипция
│       ├── text.py          # Текстовые сообщения (catch-all, последний)
│       ├── photo.py         # Фото-вложения
│       ├── forward.py       # Пересланные сообщения
│       └── buttons.py       # Обработка кнопок клавиатуры
└── services/
    ├── transcription.py     # DeepgramTranscriber (voice→text)
    ├── storage.py           # VaultStorage (daily markdown файлы)
    ├── processor.py         # ClaudeProcessor (subprocess → claude CLI)
    ├── factory.py           # Singleton factories (get_processor, get_runner, get_todoist, get_git)
    ├── grow.py              # GROW protocol: question bank, Claude prompts, draft/finalize, update_goals
    ├── session.py           # SessionStorage (JSONL-логирование)
    ├── git.py               # VaultGit (auto-commit/push)
    ├── todoist.py           # TodoistService (REST API v1)
    ├── vault_search.py      # search_vault (grep + Russian morphology)
    └── calendar_integration.py
```

```
vault/                       # Obsidian vault
├── daily/                   # Дневные записи (YYYY-MM-DD.md)
├── goals/                   # Иерархия целей (vision → yearly → monthly → weekly)
├── thoughts/                # Обработанные заметки (ideas/, learnings/, projects/, tasks/, reflections/)
├── reflections/             # GROW-рефлексии (weekly/, monthly/, quarterly/, yearly_end/, yearly_start/)
├── summaries/               # Недельные саммари
├── attachments/             # Фото по датам
├── sessions/                # JSONL-логи сессий
├── templates/               # Шаблоны заметок
├── MEMORY.md                # Долгосрочная память (курируется вручную)
└── .claude/                 # Конфиг Claude для обработки vault
    ├── skills/              # dbrain-processor, graph-builder, todoist-ai
    ├── rules/               # Форматы: daily, thoughts, goals, telegram-report
    └── CLAUDE.md            # Системные инструкции для Claude внутри vault
```

```
deploy/                      # systemd-юниты
scripts/                     # Скрипты автоматизации (process.sh, weekly.py, send_*.py)
.claude/get-shit-done/       # GSD-система управления проектом (v1.20.3)
```

### Ключевые связи

- **Хендлеры** используют **сервисы** (transcription, storage, processor, session, git)
- **VaultStorage** пишет в `vault/daily/`, **ClaudeProcessor** читает vault и создаёт файлы в `vault/thoughts/`
- **ClaudeProcessor** вызывает `claude` CLI как subprocess с таймаутом 1200с, передаёт контекст через stdin
- **VaultGit** коммитит и пушит после обработки (`chore: process daily YYYY-MM-DD`)
- **SessionStorage** — append-only JSONL в `vault/sessions/`
- FSM использует **MemoryStorage** (состояние теряется при рестарте, но GROW drafts сохраняются в vault)
- **GROW protocol** — гибридный коучинг: Claude #1 выбирает вопросы, бот задаёт по одному через FSM, Claude #2 анализирует ответы
- **APScheduler** (timezone Europe/Kyiv) — scheduled jobs для monthly report/reminders + GROW weekly/monthly/quarterly/yearly

### Порядок регистрации роутеров (важен для FSM)

commands → process → weekly → weekly_callbacks → monthly → monthly_callbacks → grow → reflection → recall → do → buttons → voice → photo → forward → text (catch-all последний)

## Правила

### Стиль кода

- **Ruff:** line-length=88, target Python 3.12, правила: E, F, I, B, UP
- **mypy:** strict=true (полная типизация обязательна)
- **pytest:** asyncio_mode=auto
- Docstrings в Google-стиле
- Async/await повсюду — синхронный код не использовать

### Именование

- Модули и переменные — snake_case
- Классы — PascalCase (DeepgramTranscriber, VaultStorage, ClaudeProcessor)
- Хендлеры — функции с префиксом по типу: `cmd_start`, `handle_voice`, `handle_text`
- Роутеры — по одному на файл хендлера, экспорт через `router = Router()`

### Процесс работы

- Любая задача больше 50 строк кода — сначала план, потом код. Без явного ОК от пользователя код не писать
- План должен описывать: какие файлы затрагиваются, что меняется, почему именно так
- Большие задачи разбивай на подзадачи и делегируй субагентам. Основной контекст держи чистым — только планирование и координация.
- Для диагностики проблем используй docker logs <container_name> --tail 100. Анализируй логи перед предложением фикса.
- После каждого фикса — докажи что работает. Напиши тест или покажи результат. Без доказательства фикс не считается завершённым.
- После исправления бага — обнови этот CLAUDE.md, добавь ошибку в раздел "Известные проблемы".

### Что НЕ делать

- Не использовать синхронные вызовы в async-контексте
- Не хардкодить токены — всё через config.py / .env
- Не менять порядок регистрации роутеров без понимания приоритетов FSM
- Не трогать `vault/.claude/` из кода бота — это конфиг для отдельного процесса Claude
- Не коммитить `.env` (уже в .gitignore)
- Не использовать `git add -A` — коммитить конкретные файлы

## Известные проблемы

- **MemoryStorage FSM** — состояние /do теряется при рестарте бота. Для продакшена нужен Redis/PostgreSQL storage
- **Нет rate-limiting** — ни для Telegram API, ни для Deepgram, ни для Todoist
- **Deepgram захардкожен на русский** — модель nova-3, нет определения языка
- **Ошибки Claude subprocess** показываются пользователю без обработки (raw errors)
- **Git push** требует токен в remote URL — если токен протухнет, push молча упадёт
- **Нет i18n** — весь интерфейс только на русском
- **Todoist-ошибки не блокируют обработку** — задача может не создаться, но процесс завершится успешно
- **Legacy reflection.py** — сохранён для обратной совместимости (кнопки в старых сообщениях). GROW weekly полностью его заменяет

## Рефакторинг (2026-02-18)

Завершён рефакторинг P0 и P1 (техдолг из анализа /techdebt). Ruff: 0 ошибок на всём проекте.

### P0 — выполнено

- **`@lru_cache` на `get_settings()`** (`config.py`) — убраны 14 дублей создания `Settings()` на каждый запрос. Теперь singleton.
- **`_run_claude(prompt, label)`** (`services/processor.py`) — извлечён единый приватный метод вместо 4 копий `subprocess.run` + exception handling (~190 строк → ~30). `generate_monthly` заодно получил недостающие `TimeoutExpired` и `FileNotFoundError`.
- **`ruff check --fix`** — автоисправлено 11 ошибок (сортировка импортов, удаление `import json`), вручную исправлены 14 ошибок E501 (длинные строки).

### P1 — выполнено

- **`run_with_progress(fn, status_msg, label, *args)`** (`bot/progress.py`) — общая async-утилита вместо 3 копий progress-polling loop в `process.py`, `weekly.py`, `do.py`.
- **`download_telegram_file(bot, file_id)`** (`bot/utils.py`) — утилита скачивания файлов из Telegram вместо 3 копий в `voice.py`, `photo.py`, `do.py`. Бросает `ValueError` при ошибке.
- **`send_formatted_report(status_msg, report)`** (`bot/utils.py`) — обёртка `format_process_report` + HTML fallback вместо 3 копий в `process.py`, `weekly.py`, `do.py`.
- **`_TZ = pytz.timezone("Europe/Kyiv")`** (`services/processor.py`) — константа на уровне модуля вместо 3 inline `import pytz` + `pytz.timezone(...)` внутри методов.

## Деплой

### Требования

- Ubuntu 22.04 VPS
- Python 3.12+, Node.js 20+, Git
- Claude Code CLI (`claude`)
- API-ключи: TELEGRAM_BOT_TOKEN, DEEPGRAM_API_KEY, TODOIST_API_KEY

### Переменные окружения (.env)

```
TELEGRAM_BOT_TOKEN=      # От @BotFather
DEEPGRAM_API_KEY=        # Транскрипция голоса
TODOIST_API_KEY=         # Управление задачами
VAULT_PATH=./vault       # Путь к Obsidian vault
ALLOWED_USER_IDS=[123]   # JSON-массив разрешённых Telegram ID
GIT_PUSH_ENABLED=true    # Автопуш в GitHub
```

### Установка

```bash
# Быстрая установка на VPS
curl -fsSL https://raw.githubusercontent.com/USER/agent-second-brain/main/bootstrap.sh | bash

# Или вручную
git clone <repo> && cd agent-second-brain
cp .env.example .env     # Заполнить токены
uv sync                  # Установить зависимости
```

### Запуск

```bash
# Локально
uv run python -m d_brain

# Через systemd (продакшен)
sudo systemctl enable --now d-brain-bot.service
sudo systemctl enable --now d-brain-process.timer   # Обработка в 21:00
sudo systemctl enable --now d-brain-weekly.timer     # Недельный дайджест
```

### Логи

```bash
sudo journalctl -u d-brain-bot -f
sudo journalctl -u d-brain-process -f
```

### Линтинг и тесты

```bash
uv run ruff check src/
uv run mypy src/
uv run pytest
```

## Уроки D.A.O.S.

Сюда автоматически записываются уроки из Step 4 (Self-Analyze) протокола D.A.O.S. Накапливаются между сессиями.

<!-- Формат записи:
### YYYY-MM-DD — [Название документа]
- Урок 1
- Урок 2
-->

### 2026-02-19 — GROW коучинг-протокол

- [x1] Модульные константы вычисляемые при импорте (`_current_year = date.today().year`) опасны в long-running процессах — значение устаревает после полуночи 31 декабря. Заменять на функцию с `date.today()` при каждом вызове
- [x1] При параллельной генерации кода субагентами — import внутри цикла и мёртвый код (subagent artifacts) неизбежны. Всегда прогонять ruff --fix + ручная проверка после сборки
- [x1] Callback data в Telegram ограничена 64 байтами — для составных идентификаторов использовать аббревиатуры (weekly->w, yearly_end->ye). Проектировать формат заранее: `grow_{type_abbr}_{index}_{action}`
- [x1] APScheduler cron trigger: для нерегулярных дат (дек 20/23/26) использовать `day="20,23,26"` вместо отдельных job'ов — один job с перечислением дней чище чем три отдельных
- [x1] FSM + scheduled jobs: scheduler не имеет доступа к FSMContext — отправлять inline-кнопку, а не пытаться стартовать FSM напрямую. Кнопка -> callback handler -> FSM start
- [x1] Гибридный AI-паттерн (2 вызова Claude за сессию, между ними чистый FSM без AI) экономит токены и даёт мгновенную реакцию пользователю. Claude #1 выбирает вопросы, бот задаёт по одному, Claude #2 анализирует ответы
- [x1] Draft-файлы как JSON с расширением .draft.md — компромисс между машиночитаемостью (JSON) и единообразием в vault (все .md). При finalize парсится JSON -> генерируется markdown
- [x1] При замене legacy-функционала (friday_reflection -> GROW weekly) оставлять старые callback handlers живыми — в чатах пользователя могут быть кнопки от старых сообщений

# Уроки D.A.O.S.

- [x1] Deprecated timezone names (Europe/Kiev vs Europe/Kyiv) — проверять согласованность timezone во всех файлах проекта
- [x1] Всегда grep-ить по паттерну бага во ВСЕХ файлах, а не только в месте где он проявился — один и тот же антипаттерн обычно повторяется


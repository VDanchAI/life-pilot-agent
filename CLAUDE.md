# Agent Second Brain

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
│   ├── keyboards.py         # Reply-клавиатура (10 кнопок, 4 строки)
│   ├── formatters.py        # HTML-форматирование отчётов
│   ├── states.py            # FSM-состояния (DoCommand, Process, Monthly, Grow, Reflection, Recall, Coach)
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
│       ├── coach.py         # Coach Mode FSM (chatting/saving) — /coach + 🤝 Коуч кнопка
│       ├── reflection.py    # DEPRECATED stub — редиректит старые кнопки на GROW
│       ├── recall.py        # /recall — поиск по vault
│       ├── vault_tools.py   # /health, /memory, /creative — утилиты vault
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
    └── calendar_integration.py  # Google Calendar MCP интеграция
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

commands → process → weekly → weekly_callbacks → monthly → monthly_callbacks → grow → reflection → recall → do → **coach** → vault_tools → buttons → voice → photo → forward → text (catch-all последний)

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
- Для диагностики проблем используй `sudo journalctl -u d-brain.service --tail 100`. Анализируй логи перед предложением фикса.
- После каждого фикса — докажи что работает. Напиши тест или покажи результат. Без доказательства фикс не считается завершённым.
- После исправления бага — обнови этот CLAUDE.md, добавь ошибку в раздел "Известные проблемы".

### Что НЕ делать

- Не использовать синхронные вызовы в async-контексте
- Не хардкодить токены — всё через config.py / .env
- Не менять порядок регистрации роутеров без понимания приоритетов FSM
- Не трогать `vault/.claude/` из кода бота — это конфиг для отдельного процесса Claude
- Не коммитить `.env` (уже в .gitignore)
- Не использовать `git add -A` — коммитить конкретные файлы

## Coaching Context (2026-coach интеграция)

Интегрированы четыре идеи из репо 2026-coach:

### Process Goals в GROW (services/grow.py)
`analyze_answers()` теперь возвращает `process_goals` — список ежедневных
контролируемых действий для каждой цели из сессии. После подтверждения
записываются в `vault/goals/coaching_context.md` через `_update_coaching_context()`.

### coaching_context.md (vault/goals/coaching_context.md)
Структурированный профиль пользователя для Claude. Обновляется автоматически
после каждой GROW-сессии и Coach-сессии. Включается во все `/do` запросы
(первые 2000 символов).

### Zoom In / Zoom Out (bot/handlers/text.py + services/processor.py)
Catch-all text handler перехватывает паттерны до обычного сохранения в vault:
- Паттерны zoom out: "zoom out", "погряз", "нет смысла", "потерял нить",
  "большая картина", "зачем всё это" → `processor.zoom_out()`
- Паттерны zoom in: "zoom in", "витаю в облаках", "что делать сегодня",
  "с чего начать", "потерялся", "за что хвататься" → `processor.zoom_in()`

### Coach Mode (bot/handlers/coach.py)
Режим диалогового коучинга. `/coach` или кнопка "🤝 Коуч" запускают FSM-сессию:
- `CoachStates.chatting` — диалог с Claude, история 20 сообщений (10 обменов)
- Голосовые сообщения поддерживаются
- "стоп" → предложение сохранить инсайты
- `processor.save_coach_insights(history)` — обновляет coaching_context.md,
  дописывает итог в daily vault

### Auto-generate 2-monthly.md (services/processor.py + bot/handlers/grow.py)
После завершения monthly GROW (`handle_confirm`):
1. Архивирует `goals/2-monthly.md` → `goals/2-monthly-{old_period}.md`
2. Генерирует новый `2-monthly.md` через `processor.generate_next_monthly_goals()`
   на основе GROW-итога и годовых целей

### Расписание APScheduler (bot/main.py + bot/handlers/grow_scheduler.py)
- **monthly_report**: 1-е число в **20:30** (не 21:00 — чтобы не пересекаться с GROW)
- **grow_weekly**: пропускает дни 1-3 месяца — monthly GROW имеет приоритет
- **grow_monthly**: 1-3 числа в 21:00
- Это предотвращает тройной флуд при совпадении начала месяца с Сб/Вс/Пн

---

## Известные проблемы

- **MemoryStorage FSM** — состояние /do теряется при рестарте бота. Для продакшена нужен Redis/PostgreSQL storage
- **Нет rate-limiting** — ни для Telegram API, ни для Deepgram, ни для Todoist (Claude subprocess имеет asyncio Lock + очередь до 2)
- **Нет i18n** — весь интерфейс только на русском
- **Todoist-ошибки не блокируют обработку** — задача может не создаться, но процесс завершится успешно
- **Нет мониторинга** — если бот упал, узнаем только когда пользователь заметит
- **Claude = SPOF** — если Claude CLI недоступен, все AI-фичи не работают

### Исправлено (2026-03-01)

- **~~Тройной флуд расписания~~** — monthly_report сдвинут на 20:30, grow_weekly пропускает дни 1-3 месяца
- **~~Дублирование вопросов GROW~~** — deferred re-queue дедуплицируется по ID вопроса
- **~~GROW draft накапливал вопросы~~** — при resume после рестарта вопросы больше не копятся

### Исправлено (2026-02-28, GSD inventory fixes)

- **~~Deepgram захардкожен на русский~~** — теперь через `TRANSCRIPTION_LANGUAGE` в .env (default: ru)
- **~~Ошибки Claude subprocess raw~~** — sanitize через `_sanitize_error()`, пользователь видит friendly messages
- **~~Git push молча падал~~** — теперь возвращает `(bool, reason)`, пользователь видит warning при ошибке sync
- **~~Claude timeout захардкожен 1200s~~** — теперь через `CLAUDE_TIMEOUT` в .env
- **~~Legacy reflection.py 251 строка~~** — заменён на stub (50 строк), старые кнопки редиректят на GROW

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
CLAUDE_TIMEOUT=1200      # Таймаут subprocess в секундах (default: 1200)
TRANSCRIPTION_LANGUAGE=ru  # Язык транскрипции Deepgram (default: ru)
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
sudo systemctl enable --now d-brain.service
sudo systemctl enable --now d-brain-process.timer   # Обработка в 21:00
sudo systemctl enable --now d-brain-weekly.timer     # Недельный дайджест
```

### Логи

```bash
sudo journalctl -u d-brain.service -f
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

### 2026-02-22 — Общие паттерны

- [x1] Баг обычно повторяется — grep по паттерну во ВСЕХ файлах (пример: deprecated timezone Europe/Kiev vs Europe/Kyiv встречался в нескольких местах)
- [x1] grep -E с || создаёт пустую альтернацию и матчит ВСЕ строки — всегда тестировать regex перед деплоем в мониторинг-скриптах
- [x1] GSD mapper agents produce redundancy by design (каждый покрывает свой аспект). При D.A.O.S. ревью мульти-агентного output — фокус на фактических ошибках и staleness, не на дедупликации между документами
- [x1] Inventory docs устаревают сразу после изменения кода — помечать FIXED с датой создаёт audit trail, но трактовать как snapshot, не как living documentation
- [x1] Перед правкой документации — проверять реальное состояние системы (systemd файл, версия в коде), а не полагаться на другие документы. Документы могут ссылаться друг на друга с ошибками

### 2026-03-01 — CLAUDE.md D.A.O.S.

- [x1] При добавлении новой .env переменной — сразу обновлять пример в CLAUDE.md (раздел Деплой). Расхождение env-примера с реальностью — частая причина путаницы при онбординге
- [x1] При добавлении нового handler-файла или сервиса — сразу добавлять в дерево архитектуры CLAUDE.md
- [x1] Changelog-разделы (Рефакторинг YYYY-MM-DD) устаревают и разбавляют рабочую документацию. Правильный паттерн: 'Исправлено (дата)' под Известными проблемами — да, отдельный 'Рефакторинг' раздел — нет

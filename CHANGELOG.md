# Changelog

## [1.3.0] — 2026-03-07

### UI & Interface
- Redesigned reply keyboard: buttons renamed to intuitive labels (`🤖 Сделать`, `🔍 Найти`, `🧹 Разобрать день`, etc.)
- Reordered buttons by usage priority
- Simplified `/help` — removed technical noise, left only functional descriptions
- Added `❓ Помощь` button to main keyboard

### Scheduler
- Added `scheduled_weekly_report` — weekly digest now fires via APScheduler (Saturday 21:00)
- GROW weekly trigger moved to Saturday 20:30 (before digest)
- Weekly report skips days 1-3 of month (monthly GROW has priority)
- Quarterly GROW: added December, moved to 22:00 (after monthly at 21:00)
- Coach profile compaction moved to 03:00 (no evening conflicts)

---

## [1.2.0] — 2026-03-03

### Coach Mode Enhancements
- Sessions saved to `vault/sessions/coach_sessions.jsonl` (sliding window, max 15)
- Monthly coach profile compaction via Claude (`compact_coach_profile`)
- `COACH_MODEL` config variable — separate model for coach (default: claude-opus-4-6)
- Structured insights output: flags, energy level, notes
- Reflection question added before saving session
- Extended stop phrases: `хватит`, `всё`, `спасибо`
- Reminder to stop every 10 turns (was 5)
- `diary_recent` + `last_coach_session` injected into coach context

### Fixes
- Google Calendar OAuth: fixed credentials path config (`GOOGLE_TOKEN_PATH`)
- Added `google-auth-oauthlib` dependency
- Scheduler: monthly_report moved to 20:30, grow_weekly skips days 1-3
- GROW: deferred question deduplication by ID

### Other
- `.gitignore` hardening: personal vault dirs excluded
- `CLAUDE.md` synced with coach architecture

---

## [1.1.0] — 2026-03-01

### New Features

**Coach Mode** (`/coach`, `🤝 Коуч` button)
- Conversational coaching FSM with Claude (20-message history / 10 exchanges)
- Voice messages supported in coach sessions
- `стоп` → saves insights to `coaching_context.md` + daily vault

**Zoom In / Zoom Out**
- Catch-all text handler intercepts focus keywords before vault save
- `zoom out` / `погряз` / `нет смысла` → big picture (vision + yearly goals)
- `zoom in` / `что делать сегодня` / `с чего начать` → concrete today's actions

**Process Goals in GROW**
- `analyze_answers()` returns `process_goals` — daily controllable actions per goal
- `coaching_context.md` auto-updated after every GROW and Coach session

**Auto-generate monthly goals**
- After monthly GROW: archives old `2-monthly.md`, generates new one based on GROW summary + yearly goals

**`coaching_context.md`**
- Structured user profile included in all `/do` requests (first 2000 chars)

### Refactoring
- `@lru_cache` on `get_settings()` — single Settings instance
- `_run_claude()` unified subprocess method (4 copies → 1)
- `run_with_progress()` shared async utility
- `download_telegram_file()`, `send_formatted_report()` extracted to utils
- ruff: 0 errors across entire project

---

## [1.0.0] — 2026-01-31

- Initial release: personal AI assistant via Telegram
- Obsidian vault integration (daily notes, thoughts, goals)
- Todoist task management
- Voice transcription via Deepgram
- GROW coaching protocol (weekly, monthly, quarterly, yearly)
- Daily processing via Claude CLI subprocess
- Weekly digest
- Git auto-commit/push for vault sync

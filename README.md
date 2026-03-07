# Life Pilot Agent

**An AI life management system designed by a practicing psychologist.**

Not another task manager. Life Pilot is a personal operating system that captures your thoughts, manages your tasks, and — most importantly — helps you reflect, set meaningful goals, and actually follow through. The coaching protocol is built on professional psychology frameworks, not generic productivity advice.

Built on [Claude Code](https://docs.anthropic.com/en/docs/claude-code) + [MCP Protocol](https://modelcontextprotocol.io/) with Google Calendar, Todoist, and Obsidian integrations.

> 🇷🇺 [Версия на русском](README.ru.md)

---

## Why Life Pilot?

Most productivity tools solve the wrong problem. They help you organize tasks — but tasks aren't the bottleneck. The bottleneck is knowing what actually matters, noticing when you're stuck, and adjusting course before months slip by.

Life Pilot closes this gap:

| Typical tool | Life Pilot |
|---|---|
| Stores notes | Captures → classifies → creates tasks → links to goals |
| You check calendar | Morning briefing arrives automatically |
| Review? What review? | Weekly digest with coaching questions |
| Goals written once, forgotten | Monthly planning sessions via guided dialogue |
| No reflection system | GROW coaching cycle: week → month → quarter → year |
| Generic prompts | Questions crafted by a practicing psychologist |

**One Telegram bot. Voice-first. Runs 24/7 on your VPS.**

---

## The Idea Behind It

This project was created by a practicing psychologist who saw a pattern in clients: people don't lack ambition or intelligence — they lack a consistent system for reflection and self-correction.

Three core principles shaped the design:

**1. Capture without friction.** Voice message in Telegram → done. No apps to open, no forms to fill. The AI handles classification, task creation, and storage. Your job is just to talk.

**2. Rhythm over motivation.** Morning plan. Evening report. Weekly reflection. Monthly review. Quarterly check-in. Yearly cycle. The system creates rhythm — and rhythm creates progress, even when motivation fades.

**3. Professional coaching, automated.** The GROW coaching protocol isn't a chatbot gimmick. The question bank was designed by a psychologist — supportive tone, no judgment, pattern recognition, gentle confrontation of avoidance. The AI adapts questions to your real data: actual goals, overdue tasks, recurring blockers.

---

## What It Does

### 📥 Capture Everything
Send anything to Telegram — the agent figures out what to do with it:
- **Voice messages** → transcribed (Deepgram) → classified → stored or tasked
- **Text** → parsed for tasks, ideas, learnings
- **Photos** → saved with context
- **Forwarded messages** → extracted and categorized

### 📋 Smart Task Management
- Auto-creates tasks in **Todoist** with correct projects and priorities
- Sorts incoming thoughts into categories: ideas, learnings, projects, reflections
- Detects stale tasks and prompts you to act
- Tracks transfers and overdue patterns

### 📅 Daily Rhythm
- **Morning plan** — sent automatically with today's calendar events, tasks, and priorities
- **Evening report** — summary of what was captured and processed
- **Weekly digest** — progress review with key metrics
- **Monthly planning** — guided goal-setting session via interactive questions

### 🧭 GROW Coaching Protocol
The heart of Life Pilot. A structured reflection system based on the GROW framework (Goal → Reality → Options → Will), designed by a practicing psychologist.

**How it works:**
1. AI analyzes your data — goals, completed/overdue tasks, recurring patterns, previous reflections
2. Selects 2-4 questions from a curated bank, adapted to your specific situation
3. Questions arrive one at a time — you answer with text or voice (multiple messages per question)
4. AI summarizes insights and proposes concrete goal updates
5. You confirm — goals auto-update in your vault

**Coaching cycles:**
- **Weekly** (Saturday) — what worked, what didn't, energy patterns, focus for next week
- **Monthly** (1st) — goal relevance, priority reset, pattern analysis, resource assessment
- **Quarterly** — deep dive into yearly goals, course correction, removing what doesn't serve you
- **Yearly** — December: gratitude, lessons learned, year review. January: vision alignment, new goals, first steps

**What makes it different from generic reflection prompts:**
- Questions are psychologically informed — supportive tone, no judgment, pattern recognition
- AI doesn't ask random questions — it picks based on your actual overdue tasks, skipped goals, repeated blockers
- Deferred questions carry over, skipped sessions are tracked — nothing falls through the cracks
- 3 reminder attempts per session — persistent but not annoying
- All reflections stored in structured markdown for long-term self-awareness

### 🤖 AI Commands (Keyboard Buttons)

| Button | What it does |
|---|---|
| 🤖 Сделать | Free-form query to Claude — search notes, analyze, advise |
| 🔍 Найти | Search your vault |
| 🤝 Коуч | Start a conversational coaching session |
| 🧹 Разобрать день | Run Claude on today's inbox — sort, classify, create tasks |
| 📋 План | Morning briefing: calendar + tasks + priorities |
| 📅 Неделя | Weekly progress digest |
| 📊 Статус | Current system status |
| ℹ️ Помощь | Command reference |
| 🎲 Находка | Random insight from your vault |
| 🏥 Здоровье | Vault health check |
| 🧠 Память | Your MEMORY.md file |

### 🔭 Zoom In / Zoom Out

Send a message with a trigger phrase and the bot instantly shifts your perspective:

**Zoom Out** — when you're lost in details and need the big picture:
> *"zoom out", "погряз в деталях", "потерял нить", "большая картина", "зачем всё это"*

Claude reminds you of your vision, yearly goals, and why this work matters.

**Zoom In** — when you're floating in abstractions and need to act:
> *"zoom in", "витаю в облаках", "что делать сегодня", "с чего начать", "за что хвататься"*

Claude gives you a concrete action for right now based on your tasks and priorities.

### 🤝 Coach Mode

An on-demand conversational coaching session — not a scheduled protocol, but a real-time dialogue you initiate when you need it.

**Start:** `/coach` command or the 🤝 Coach button.

**How it works:**
- Talk freely — text or voice. Claude reads your message and determines your current state:
  - **Stream** — venting, jumping between topics, thinking out loud → reflection + space
  - **Focus** — circling one topic, comparing options → deepening, scaling, provocation
  - **Readiness** — insight emerged, you're formulating a conclusion → anchor it, make it concrete
- Knows your goals, recent diary entries, and last session summary — uses this only when it naturally fits the conversation
- One question per message, no advice without request, no lists — just dialogue
- When done, write "stop" → Claude generates a closing reflection: *"You started with X, arrived at Y — what matters most?"*
- You answer → save insights → they go into your profile and diary, carried into future sessions

**What it is not:** a GROW protocol, therapy, or task assistant. It's a skilled listener who knows your context.

### 🔄 Integrations via MCP

| Service | What it does |
|---|---|
| **Google Calendar** | Morning plan, schedule awareness, event context |
| **Todoist** | Task creation, project sorting, priority management |
| **Obsidian** | Note storage, knowledge graph, goal tracking |
| **GitHub** | Auto-commit and sync of all vault changes |

---

## Architecture

```
┌──────────────┐     ┌──────────────┐     ┌──────────────────┐
│   Telegram   │────▶│  VPS Server  │────▶│   Claude Code    │
│   (input)    │     │    (bot)     │     │    (AI agent)    │
└──────────────┘     └──────────────┘     └──────────────────┘
                                            │    │    │
                                            ▼    ▼    ▼
                                     ┌────────┐┌────────┐┌────────┐
                                     │Todoist ││Google  ││Obsidian│
                                     │(tasks) ││Calendar││(notes) │
                                     └────────┘└────────┘└────────┘
```

### Tech Stack

- **Language:** Python 3.12+
- **Package manager:** uv (astral.sh)
- **Telegram framework:** aiogram 3.0+ (async)
- **Transcription:** Deepgram SDK (nova-3)
- **Tasks:** Todoist API
- **AI engine:** Claude Code CLI (subprocess)
- **MCP servers:** Todoist, Google Calendar
- **Storage:** File system (Obsidian vault, Markdown + JSONL sessions)
- **Deploy:** systemd on Ubuntu VPS
- **Code quality:** ruff + mypy strict + pytest

### Project Structure

```
src/d_brain/
├── __main__.py              # Entry point
├── config.py                # Pydantic Settings from .env
├── bot/
│   ├── main.py              # Bot init, router registration
│   ├── keyboards.py         # Reply keyboard (11 buttons)
│   ├── formatters.py        # HTML report formatting
│   ├── progress.py          # Async progress utility
│   ├── utils.py             # Shared helpers
│   ├── states.py            # FSM states
│   └── handlers/
│       ├── commands.py      # /start, /help, /status, /plan
│       ├── process.py       # ⚙️ Process — Claude inbox processing
│       ├── do.py            # ✨ Request — free-form Claude queries
│       ├── weekly.py        # 📅 Weekly digest
│       ├── grow.py          # 🧭 GROW coaching sessions (FSM)
│       ├── grow_scheduler.py # Scheduled GROW reminders
│       ├── voice.py         # Voice → transcription → storage
│       ├── text.py          # Text messages (catch-all)
│       ├── photo.py         # Photo attachments
│       ├── forward.py       # Forwarded messages
│       └── buttons.py       # Keyboard button routing
└── services/
    ├── transcription.py     # DeepgramTranscriber
    ├── storage.py           # VaultStorage (daily markdown)
    ├── processor.py         # ClaudeProcessor (subprocess)
    ├── grow.py              # GROW session logic, question bank, drafts
    ├── session.py           # SessionStorage (JSONL logging)
    ├── calendar_integration.py  # Google Calendar sync
    └── git.py               # Auto-commit & push

vault/                       # Obsidian vault
├── daily/                   # Daily entries (YYYY-MM-DD.md)
├── goals/                   # Goal hierarchy (vision → yearly → monthly → weekly)
├── thoughts/                # Classified notes (ideas/ learnings/ projects/)
├── reflections/             # GROW coaching sessions (weekly/ monthly/ quarterly/ yearly/)
├── summaries/               # Weekly summaries
├── templates/               # Note templates
├── sessions/                # JSONL session logs
├── attachments/             # Photos by date
└── .claude/                 # Claude config for vault processing

deploy/                      # systemd units
scripts/                     # Automation (process.sh, weekly.py, send_*.py)
```

---

## Quick Start

### Prerequisites

| Component | Purpose | Cost |
|---|---|---|
| Claude Pro/Max | AI agent | $20/mo |
| VPS (non-RU/BY) | 24/7 bot hosting | ~$5/mo |
| GitHub | Backup & sync | Free |
| Deepgram | Voice transcription | Free ($200 credit) |
| Todoist | Task management | Free / $4/mo Pro |

### 1. Clone & Configure

```bash
git clone https://github.com/YOUR_USERNAME/life-pilot-agent.git
cd life-pilot-agent
cp .env.example .env
```

Edit `.env` with your keys:

```env
TELEGRAM_BOT_TOKEN=       # From @BotFather
DEEPGRAM_API_KEY=         # console.deepgram.com
TODOIST_API_KEY=          # Todoist → Settings → Integrations
VAULT_PATH=./vault
ALLOWED_USER_IDS=[123]    # Your Telegram ID (from @userinfobot)
COACH_MODEL=claude-opus-4-6  # Model for Coach Mode (use a capable one)
```

### 2. Set Up Your Vault

Create the vault directory structure and fill in your context files:

```bash
mkdir -p vault/{daily,goals,thoughts/{ideas,learnings,projects,reflections,tasks},reflections/{weekly,monthly,quarterly,yearly_start,yearly_end},summaries,sessions,attachments,templates}
touch vault/daily/.gitkeep vault/attachments/.gitkeep
```

**`vault/goals/coaching_context.md`** — the most important file. Coach Mode and all AI features read this to understand who you are:

```markdown
# Coaching Context

## Profile

- Timezone: Europe/London
- Role: [your role / occupation]
- Working style: [remote / office / mixed]

## Current Goals and Daily Actions

| Goal (outcome) | Daily action |
|---|---|
| [Your main goal] | [What you do daily to move toward it] |
| [Second goal] | [Daily action] |

## What Gives Energy

- [e.g., deep focused work in the morning]
- [e.g., physical activity]

## What Drains Energy

- [e.g., endless meetings without outcomes]
- [e.g., unclear priorities]

## Current Focus (this month)

[2-3 sentences: what are you working on right now, what matters most]

## Known Patterns and Blockers

- [e.g., tend to avoid difficult conversations]
- [e.g., lose focus when working on too many things at once]
```

**`vault/goals/1-yearly-YYYY.md`** — yearly goals (replace YYYY with current year):

```markdown
# Goals YYYY

## [Goal Area 1]
- Outcome: [what does success look like]
- Key milestones: [main checkpoints]

## [Goal Area 2]
- Outcome: [what does success look like]
```

**`vault/goals/2-monthly.md`** — current month priorities:

```markdown
# Monthly Goals — [Month YYYY]

## Focus
[Main theme or intention for this month]

## Goals
- [ ] [Goal 1]
- [ ] [Goal 2]
```

> **Without `coaching_context.md` the Coach Mode will work, but without knowing your goals and context — it's just a generic chatbot. Fill it in first.**

### 3. Install & Run

```bash
# Install dependencies
uv sync

# Run locally
uv run python -m d_brain

# Or deploy with systemd (production)
sudo cp deploy/*.service deploy/*.timer /etc/systemd/system/
sudo systemctl enable --now d-brain-bot.service
sudo systemctl enable --now d-brain-process.timer    # Evening processing at 21:00
sudo systemctl enable --now d-brain-weekly.timer      # Weekly digest
```

### 4. Customize Schedule

All report and coaching times are configured in `src/d_brain/bot/main.py` → `create_scheduler()`. Default timezone is `Europe/Chisinau`. Adjust to your rhythm:

| Event | Default time | What to change |
|---|---|---|
| Morning plan | 08:00 | `send_morning_plan` cron hour |
| Evening processing | 21:00 | `d-brain-process.timer` or scheduler job |
| Weekly GROW coaching | Saturday 21:00 | `scheduled_grow_weekly` cron day/hour |
| Monthly GROW coaching | 1st of month 21:00 | `scheduled_grow_monthly` cron day/hour |
| Timezone | Europe/Chisinau | `timezone` parameter in `create_scheduler()` |

> ⚠️ **Important:** Set the timezone and times that match your daily routine. The system works best when morning plan arrives before your day starts and evening report comes after your workday ends.

### 5. Verify

```bash
# Check bot is running
sudo journalctl -u d-brain-bot -f

# Run linters
uv run ruff check src/
uv run mypy src/
uv run pytest
```

---

## How It Differs from the Original

This project started as a fork of [smixs/agent-second-brain](https://github.com/smixs/agent-second-brain) and evolved into a different product:

| Feature | Original | Life Pilot |
|---|---|---|
| Design philosophy | Tech-first | Psychology-first |
| Google Calendar integration | ❌ | ✅ Morning plan with schedule |
| Automated daily rhythm | ❌ | ✅ Morning plan + evening report |
| Weekly digest + coaching | ❌ | ✅ Progress review with questions |
| GROW coaching protocol | ❌ | ✅ Weekly / monthly / quarterly / yearly |
| Monthly planning | ❌ | ✅ Guided goal-setting session |
| Smart task management | Basic | Stale detection, transfers, updates |
| Project sorting | Single inbox | Multi-project classification |
| Interactive buttons | Basic | 11-button keyboard with full workflows |
| Bug fixes | — | Multiple hidden issues resolved |
| Code quality | — | ruff 0 errors, mypy strict 0 errors |

---

## License

MIT

---

## Author

Created by a practicing psychologist who builds AI tools for personal development and self-awareness.

## Credits

Inspired by [smixs/agent-second-brain](https://github.com/smixs/agent-second-brain). Built with [Claude Code](https://docs.anthropic.com/en/docs/claude-code) and [MCP Protocol](https://modelcontextprotocol.io/).

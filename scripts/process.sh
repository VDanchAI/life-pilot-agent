#!/bin/bash
set -e

# PATH for systemd (claude, uv, npx in ~/.local/bin and node)
export PATH="$HOME/.local/bin:/usr/local/bin:/usr/bin:/bin:$PATH"
# Set HOME if needed: export HOME="/home/ubuntu"

# Paths
PROJECT_DIR="${PROJECT_DIR:-$(cd "$(dirname "$0")/.." && pwd)}"
VAULT_DIR="$PROJECT_DIR/vault"
ENV_FILE="$PROJECT_DIR/.env"

# Load environment variables
if [ -f "$ENV_FILE" ]; then
    export $(grep -v '^#' "$ENV_FILE" | xargs)
fi

# Check token
if [ -z "$TELEGRAM_BOT_TOKEN" ]; then
    echo "ERROR: TELEGRAM_BOT_TOKEN not set"
    exit 1
fi

# Date and chat_id
TODAY=$(date +%Y-%m-%d)
CHAT_ID="${ALLOWED_USER_IDS//[\[\]]/}"  # remove brackets from [123456]

cd "$PROJECT_DIR"  # MCP configured for project root

echo "=== d-brain processing for $TODAY ==="

# ── ORIENT: skip if daily is empty ──
DAILY_FILE="$VAULT_DIR/daily/$TODAY.md"
if [ ! -f "$DAILY_FILE" ]; then
    echo "# $TODAY" > "$DAILY_FILE"
fi
DAILY_SIZE=$(wc -c < "$DAILY_FILE" 2>/dev/null || echo "0")
if [ "$DAILY_SIZE" -lt 50 ]; then
    echo "ORIENT: daily/$TODAY.md is empty ($DAILY_SIZE bytes) — skipping Claude processing"
    cd "$VAULT_DIR"
    uv run .claude/skills/graph-builder/scripts/analyze.py 2>/dev/null || true
    cd "$PROJECT_DIR"
    git add -A
    git commit -m "chore: process daily $TODAY" || true
    git push || true
    echo "=== Done (empty daily, graph-only) ==="
    exit 0
fi

# Run Claude with --dangerously-skip-permissions and MCP
REPORT=$(claude --print --dangerously-skip-permissions \
    --mcp-config "$PROJECT_DIR/mcp-config.json" \
    -p "Today is $TODAY. Execute daily processing according to dbrain-processor skill." \
    2>&1) || true

echo "=== Claude output ==="
echo "$REPORT"
echo "===================="

# ── POST: graph rebuild + memory decay (non-critical) ──
cd "$VAULT_DIR"
uv run .claude/skills/graph-builder/scripts/analyze.py 2>/dev/null || echo "Graph rebuild failed (non-critical)"
python3 .claude/skills/agent-memory/scripts/memory-engine.py decay . 2>/dev/null || echo "Memory decay failed (non-critical)"
cd "$PROJECT_DIR"

# Git commit with error reporting to Telegram
git add -A
git commit -m "chore: process daily $TODAY" || true

if ! git pull --rebase origin main 2>/tmp/git_error.log; then
    GIT_ERR=$(cat /tmp/git_error.log)
    curl -s -X POST "https://api.telegram.org/bot$TELEGRAM_BOT_TOKEN/sendMessage" \
        -d "chat_id=$CHAT_ID" \
        -d "text=⚠️ GIT SYNC ERROR (pull --rebase):%0A$GIT_ERR"
    git rebase --abort 2>/dev/null || true
fi

if ! git push 2>/tmp/git_error.log; then
    GIT_ERR=$(cat /tmp/git_error.log)
    curl -s -X POST "https://api.telegram.org/bot$TELEGRAM_BOT_TOKEN/sendMessage" \
        -d "chat_id=$CHAT_ID" \
        -d "text=⚠️ GIT SYNC ERROR (push):%0A$GIT_ERR"
fi

# Send to Telegram
if [ -n "$REPORT" ] && [ -n "$CHAT_ID" ]; then
    echo "=== Sending to Telegram ==="
    curl -s -X POST "https://api.telegram.org/bot$TELEGRAM_BOT_TOKEN/sendMessage" \
        -d "chat_id=$CHAT_ID" \
        -d "text=$REPORT" \
        -d "parse_mode=HTML" || \
    # Fallback: send without HTML parsing
    curl -s -X POST "https://api.telegram.org/bot$TELEGRAM_BOT_TOKEN/sendMessage" \
        -d "chat_id=$CHAT_ID" \
        -d "text=$REPORT"
fi

echo "=== Done ==="

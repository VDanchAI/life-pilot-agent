#!/bin/bash
# process-v2.sh — 3-phase daily pipeline with structured logging
# Parallel testing alongside process.sh for 7 days

# ── ERROR HANDLING ──
# No set -e: we handle errors manually per phase
set -uo pipefail

# ── PATHS ──
# Set HOME if needed: export HOME="/home/ubuntu"
export PATH="$HOME/.local/bin:/usr/local/bin:/usr/bin:/bin:$PATH"
export TZ="${TZ:-Europe/Kyiv}"

PROJECT_DIR="${PROJECT_DIR:-$(cd "$(dirname "$0")/.." && pwd)}"
VAULT_DIR="$PROJECT_DIR/vault"
ENV_FILE="$PROJECT_DIR/.env"
LOG_DIR="$PROJECT_DIR/logs"
TODAY=$(date +%Y-%m-%d)

LOG_FILE="$LOG_DIR/process-v2.log"
ERR_LOG="$LOG_DIR/process-v2-errors.log"

mkdir -p "$LOG_DIR" "$VAULT_DIR/.session"

# ── LOAD ENV ──
if [ -f "$ENV_FILE" ]; then
    export $(grep -v '^#' "$ENV_FILE" | xargs)
fi

if [ -z "${TELEGRAM_BOT_TOKEN:-}" ]; then
    echo "ERROR: TELEGRAM_BOT_TOKEN not set"
    exit 1
fi

CHAT_ID="${ALLOWED_USER_IDS:-}"
CHAT_ID="${CHAT_ID//[\[\]]/}"
PHASES_OK=0
PHASES_TOTAL=0
SCRIPT_START=$(date +%s)

# ── LOGGING ──
log() {
    local phase="$1" status="$2" duration="$3" details="$4"
    local ts=$(date '+%Y-%m-%d %H:%M:%S')
    printf "%s | %-8s | %-4s | %6s | %s\n" "$ts" "$phase" "$status" "$duration" "$details" \
        >> "$LOG_FILE"
}

log_error() {
    log "$@"
    local phase="$1" status="$2" duration="$3" details="$4"
    local ts=$(date '+%Y-%m-%d %H:%M:%S')
    printf "%s | %-8s | %-4s | %6s | %s\n" "$ts" "$phase" "$status" "$duration" "$details" \
        >> "$ERR_LOG"
}

# ── JSON EXTRACTION ──
extract_json() {
    python3 -c "
import sys, json, re
text = sys.stdin.read()
# Try to find JSON objects in output
matches = re.findall(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', text, re.DOTALL)
for m in matches:
    try:
        data = json.loads(m)
        json.dump(data, sys.stdout, ensure_ascii=False, indent=2)
        sys.exit(0)
    except: pass
# Fallback
json.dump({'error': 'no valid JSON found', 'raw_length': len(text)}, sys.stdout)
sys.exit(1)
"
}

# ── VARIABLES ──
DAILY_FILE="$VAULT_DIR/daily/$TODAY.md"
HANDOFF_FILE="$VAULT_DIR/.session/handoff.md"
GRAPH_FILE="$VAULT_DIR/.graph/vault-graph.json"
SESSION_DIR="$VAULT_DIR/.session"
CAPTURE_FILE="$SESSION_DIR/capture.json"
EXECUTE_FILE="$SESSION_DIR/execute.json"
YEARLY_GOALS=$(ls "$VAULT_DIR/goals/1-yearly-"*.md 2>/dev/null | tail -1)
YEARLY_GOALS_NAME=$(basename "$YEARLY_GOALS" 2>/dev/null || echo "1-yearly.md")

MCP_PROMPT="CRITICAL: MCP loads in 10-30 seconds. You are NOT in subprocess.
Algorithm: 1) Call. 2) Error? Wait 10 sec. 3) Call again. 4) Wait 20 sec. 5) Call — GUARANTEED to work.
DO NOT say MCP unavailable. It is available. Just wait and call."

VAULT_FILES=$(find "$VAULT_DIR" -name "*.md" | wc -l)
DAILY_SIZE=0

# ── START ──
log "START" "---" "---" "date=$TODAY vault_files=$VAULT_FILES"

# ══════════════════════════════════════════════════
# ORIENT PHASE
# ══════════════════════════════════════════════════
PHASE_START=$(date +%s)
((PHASES_TOTAL++))

if [ ! -f "$DAILY_FILE" ]; then
    echo "# $TODAY" > "$DAILY_FILE"
fi
DAILY_SIZE=$(wc -c < "$DAILY_FILE" 2>/dev/null || echo "0")

# Check handoff
if [ ! -f "$HANDOFF_FILE" ]; then
    mkdir -p "$SESSION_DIR"
    printf -- "---\nupdated: %s\n---\n\n## Last Session\n(none)\n\n## Observations\n" "$(date -Iseconds)" > "$HANDOFF_FILE"
fi

# Check graph age
GRAPH_AGE="n/a"
if [ -f "$GRAPH_FILE" ]; then
    GRAPH_AGE="$(( ($(date +%s) - $(stat -c %Y "$GRAPH_FILE" 2>/dev/null || echo 0)) / 86400 ))d"
fi

PHASE_DURATION=$(( $(date +%s) - PHASE_START ))

if [ "$DAILY_SIZE" -lt 50 ]; then
    log "ORIENT" "SKIP" "${PHASE_DURATION}s" "daily=${DAILY_SIZE}b reason=empty graph_age=$GRAPH_AGE"

    # Graph-only mode
    cd "$VAULT_DIR"
    uv run .claude/skills/graph-builder/scripts/analyze.py 2>/dev/null || true
    cd "$PROJECT_DIR"

    git add -A
    git commit -m "chore: process daily $TODAY" 2>/dev/null || true
    git push 2>/dev/null || true

    log "END" "SKIP" "$(( $(date +%s) - SCRIPT_START ))s" "phases=0/0 reason=empty_daily"
    exit 0
fi

log "ORIENT" "OK" "${PHASE_DURATION}s" "daily=${DAILY_SIZE}b handoff=OK graph_age=$GRAPH_AGE"
((PHASES_OK++))

# ══════════════════════════════════════════════════
# CAPTURE PHASE
# ══════════════════════════════════════════════════
PHASE_START=$(date +%s)
((PHASES_TOTAL++))

cd "$VAULT_DIR"

CAPTURE_RAW=$(claude --print --dangerously-skip-permissions \
    -p "Today is $TODAY. Read .claude/skills/dbrain-processor/phases/capture.md and execute Phase 1.
Read daily/$TODAY.md, goals/3-weekly.md, goals/2-monthly.md, goals/$YEARLY_GOALS_NAME.
Classify each entry. Return ONLY JSON." \
    2>&1) || true

# Save raw output
echo "$CAPTURE_RAW" > "$LOG_DIR/claude-output-$TODAY-capture.txt"

# Extract JSON
echo "$CAPTURE_RAW" | extract_json > "$CAPTURE_FILE" 2>/dev/null

PHASE_DURATION=$(( $(date +%s) - PHASE_START ))
CAPTURE_SIZE=$(wc -c < "$CAPTURE_FILE" 2>/dev/null || echo "0")

if grep -q '"error"' "$CAPTURE_FILE" 2>/dev/null; then
    log_error "CAPTURE" "FAIL" "${PHASE_DURATION}s" "size=${CAPTURE_SIZE}b reason=json_parse_failed"

    # Fallback to monolith mode
    REPORT=$(claude --print --dangerously-skip-permissions \
        --mcp-config "$PROJECT_DIR/mcp-config.json" \
        -p "Today is $TODAY. Execute daily processing according to dbrain-processor skill.
$MCP_PROMPT" \
        2>&1) || true

    echo "$REPORT" > "$LOG_DIR/claude-output-$TODAY-monolith.txt"
    log "FALLBACK" "OK" "---" "mode=monolith report_len=${#REPORT}"
else
    log "CAPTURE" "OK" "${PHASE_DURATION}s" "size=${CAPTURE_SIZE}b"
    ((PHASES_OK++))

    # ══════════════════════════════════════════════════
    # EXECUTE PHASE
    # ══════════════════════════════════════════════════
    PHASE_START=$(date +%s)
    ((PHASES_TOTAL++))

    export MCP_TIMEOUT=30000
    export MAX_MCP_OUTPUT_TOKENS=50000

    EXECUTE_RAW=$(claude --print --dangerously-skip-permissions \
        --mcp-config "$PROJECT_DIR/mcp-config.json" \
        -p "Today is $TODAY. Read .claude/skills/dbrain-processor/phases/execute.md and execute Phase 2.
Read .session/capture.json for input data.
Read business/_index.md and projects/_index.md for context.
Create tasks in Todoist, save thoughts, update CRM. Return ONLY JSON.
$MCP_PROMPT" \
        2>&1) || true

    echo "$EXECUTE_RAW" > "$LOG_DIR/claude-output-$TODAY-execute.txt"
    echo "$EXECUTE_RAW" | extract_json > "$EXECUTE_FILE" 2>/dev/null

    PHASE_DURATION=$(( $(date +%s) - PHASE_START ))
    EXECUTE_SIZE=$(wc -c < "$EXECUTE_FILE" 2>/dev/null || echo "0")

    if grep -q '"error"' "$EXECUTE_FILE" 2>/dev/null; then
        log_error "EXECUTE" "FAIL" "${PHASE_DURATION}s" "size=${EXECUTE_SIZE}b reason=json_parse_failed"
    else
        log "EXECUTE" "OK" "${PHASE_DURATION}s" "size=${EXECUTE_SIZE}b"
        ((PHASES_OK++))
    fi

    # ══════════════════════════════════════════════════
    # REFLECT PHASE
    # ══════════════════════════════════════════════════
    PHASE_START=$(date +%s)
    ((PHASES_TOTAL++))

    REPORT=$(claude --print --dangerously-skip-permissions \
        -p "Today is $TODAY. Read .claude/skills/dbrain-processor/phases/reflect.md and execute Phase 3.
Read .session/capture.json and .session/execute.json for input data.
Read MEMORY.md, .session/handoff.md, .graph/health-history.json.
Generate HTML report, update MEMORY, record observations.
Return ONLY RAW HTML (for Telegram)." \
        2>&1) || true

    echo "$REPORT" > "$LOG_DIR/claude-output-$TODAY-reflect.txt"

    # Clean HTML comments
    REPORT=$(echo "$REPORT" | sed '/<!--/,/-->/d')

    PHASE_DURATION=$(( $(date +%s) - PHASE_START ))

    if [ ${#REPORT} -lt 20 ]; then
        log_error "REFLECT" "FAIL" "${PHASE_DURATION}s" "report_len=${#REPORT} reason=too_short"
    else
        log "REFLECT" "OK" "${PHASE_DURATION}s" "report_len=${#REPORT}"
        ((PHASES_OK++))
    fi
fi

cd "$PROJECT_DIR"

# ══════════════════════════════════════════════════
# POST PHASE: graph rebuild + memory decay
# ══════════════════════════════════════════════════
PHASE_START=$(date +%s)
((PHASES_TOTAL++))

cd "$VAULT_DIR"

GRAPH_RESULT="ok"
uv run .claude/skills/graph-builder/scripts/analyze.py 2>/dev/null || GRAPH_RESULT="fail"

DECAY_RESULT="ok"
DECAY_OUTPUT=$(python3 .claude/skills/agent-memory/scripts/memory-engine.py decay . 2>&1) || DECAY_RESULT="fail"
DECAY_COUNT=$(echo "$DECAY_OUTPUT" | grep -oP 'decayed:\s+\K\d+' || echo "0")

cd "$PROJECT_DIR"

PHASE_DURATION=$(( $(date +%s) - PHASE_START ))

if [ "$GRAPH_RESULT" = "ok" ] && [ "$DECAY_RESULT" = "ok" ]; then
    log "POST" "OK" "${PHASE_DURATION}s" "graph=$GRAPH_RESULT decay=$DECAY_RESULT decay_count=$DECAY_COUNT"
    ((PHASES_OK++))
else
    log_error "POST" "WARN" "${PHASE_DURATION}s" "graph=$GRAPH_RESULT decay=$DECAY_RESULT"
    ((PHASES_OK++))  # non-critical, still count as success
fi

# ══════════════════════════════════════════════════
# GIT PHASE
# ══════════════════════════════════════════════════
PHASE_START=$(date +%s)
((PHASES_TOTAL++))

git add -A
COMMIT_HASH=""
if git commit -m "chore: process daily $TODAY (v2)" 2>/dev/null; then
    git pull --rebase origin main 2>/dev/null || { git rebase --abort 2>/dev/null || true; }
    git push 2>/dev/null && COMMIT_HASH=$(git rev-parse --short HEAD 2>/dev/null)
fi

PHASE_DURATION=$(( $(date +%s) - PHASE_START ))

if [ -n "$COMMIT_HASH" ]; then
    log "GIT" "OK" "${PHASE_DURATION}s" "commit=$COMMIT_HASH"
    ((PHASES_OK++))
else
    log "GIT" "SKIP" "${PHASE_DURATION}s" "reason=nothing_to_commit_or_push_failed"
fi

# ══════════════════════════════════════════════════
# TELEGRAM PHASE
# ══════════════════════════════════════════════════
PHASE_START=$(date +%s)
((PHASES_TOTAL++))

REPORT_CLEAN="${REPORT:-No report generated}"
TG_RESULT="fail"
MSG_ID=""

if [ -n "${REPORT_CLEAN}" ] && [ -n "$CHAT_ID" ]; then
    RESPONSE=$(curl -s -X POST "https://api.telegram.org/bot$TELEGRAM_BOT_TOKEN/sendMessage" \
        -d "chat_id=$CHAT_ID" \
        -d "text=$REPORT_CLEAN" \
        -d "parse_mode=HTML" 2>/dev/null)

    if echo "$RESPONSE" | grep -q '"ok":true'; then
        TG_RESULT="ok"
        MSG_ID=$(echo "$RESPONSE" | python3 -c "import sys,json; print(json.load(sys.stdin).get('result',{}).get('message_id',''))" 2>/dev/null)
    else
        # Fallback without HTML
        RESPONSE=$(curl -s -X POST "https://api.telegram.org/bot$TELEGRAM_BOT_TOKEN/sendMessage" \
            -d "chat_id=$CHAT_ID" \
            -d "text=$REPORT_CLEAN" 2>/dev/null)
        if echo "$RESPONSE" | grep -q '"ok":true'; then
            TG_RESULT="ok_plain"
            MSG_ID=$(echo "$RESPONSE" | python3 -c "import sys,json; print(json.load(sys.stdin).get('result',{}).get('message_id',''))" 2>/dev/null)
        fi
    fi
fi

PHASE_DURATION=$(( $(date +%s) - PHASE_START ))

if [ "$TG_RESULT" != "fail" ]; then
    log "TELEGRAM" "OK" "${PHASE_DURATION}s" "mode=$TG_RESULT msg_id=$MSG_ID"
    ((PHASES_OK++))
else
    log_error "TELEGRAM" "FAIL" "${PHASE_DURATION}s" "chat_id=$CHAT_ID"
fi

# ══════════════════════════════════════════════════
# END
# ══════════════════════════════════════════════════
TOTAL_DURATION=$(( $(date +%s) - SCRIPT_START ))
log "END" "---" "${TOTAL_DURATION}s" "phases=$PHASES_OK/$PHASES_TOTAL"

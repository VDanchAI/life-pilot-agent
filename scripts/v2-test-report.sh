#!/bin/bash
# v2-test-report.sh — Parse process-v2.log and generate test report
# Usage: bash scripts/v2-test-report.sh [--telegram] [--days N]

PROJECT_DIR="${PROJECT_DIR:-$(cd "$(dirname "$0")/.." && pwd)}"
LOG_FILE="$PROJECT_DIR/logs/process-v2.log"
ENV_FILE="$PROJECT_DIR/.env"

# Parse args
SEND_TELEGRAM=false
DAYS=7
while [[ $# -gt 0 ]]; do
    case "$1" in
        --telegram) SEND_TELEGRAM=true; shift ;;
        --days) DAYS="$2"; shift 2 ;;
        *) shift ;;
    esac
done

if [ ! -f "$LOG_FILE" ]; then
    echo "No log file found at $LOG_FILE"
    exit 1
fi

# Date range
END_DATE=$(date +%Y-%m-%d)
START_DATE=$(date -d "$END_DATE - $DAYS days" +%Y-%m-%d 2>/dev/null || date -v-${DAYS}d +%Y-%m-%d)

# Filter log lines within date range
FILTERED=$(awk -v start="$START_DATE" -v end="$END_DATE" '$1 >= start && $1 <= end' "$LOG_FILE")

# Count runs (START lines)
RUNS=$(echo "$FILTERED" | grep "| START " | wc -l)

# Count full successes (END lines where phases match N/N)
FULL_SUCCESS=$(echo "$FILTERED" | grep "| END " | grep -oP 'phases=\K\d+/\d+' | awk -F/ '$1==$2' | wc -l)

# Count skipped (END with reason=empty_daily)
SKIPPED=$(echo "$FILTERED" | grep "| END " | grep "empty_daily" | wc -l)

# Partial = runs - full_success - skipped
PARTIAL=$(( RUNS - FULL_SUCCESS - SKIPPED ))
[ "$PARTIAL" -lt 0 ] && PARTIAL=0

# Phase stats function
phase_stats() {
    local phase="$1"
    local total=$(echo "$FILTERED" | grep "| $phase " | grep -v "START\|END" | wc -l)
    local ok=$(echo "$FILTERED" | grep "| $phase " | grep "| OK " | wc -l)
    local skip=$(echo "$FILTERED" | grep "| $phase " | grep "| SKIP " | wc -l)
    local fail=$(echo "$FILTERED" | grep "| $phase " | grep -E "FAIL|WARN" | wc -l)
    if [ "$total" -gt 0 ]; then
        local pct=$(( ok * 100 / total ))
        printf "  %-10s %d/%d (%d%%)" "$phase:" "$ok" "$total" "$pct"
        [ "$skip" -gt 0 ] && printf "  [%d skipped]" "$skip"
        [ "$fail" -gt 0 ] && printf "  <- needs attention"
        printf "\n"
    fi
}

# Timing stats (from END lines)
TIMINGS=$(echo "$FILTERED" | grep "| END " | grep -oP '\|\s+\K\d+(?=s\s+\|)' 2>/dev/null)
if [ -n "$TIMINGS" ]; then
    AVG=$(echo "$TIMINGS" | awk '{s+=$1; n++} END {if(n>0) printf "%d", s/n; else print "0"}')
    MIN=$(echo "$TIMINGS" | sort -n | head -1)
    MAX=$(echo "$TIMINGS" | sort -n | tail -1)
    TIMING_LINE="Timing: avg=${AVG}s min=${MIN}s max=${MAX}s"
else
    TIMING_LINE="Timing: no data"
fi

# Collect errors
ERRORS=$(echo "$FILTERED" | grep -E "\| FAIL \|| error" | head -10)

# Verdict
if [ "$RUNS" -eq 0 ]; then
    VERDICT="NO DATA"
elif [ "$FULL_SUCCESS" -eq "$RUNS" ]; then
    VERDICT="READY FOR PRODUCTION"
elif [ "$PARTIAL" -le 1 ] && [ "$FULL_SUCCESS" -ge $(( RUNS / 2 )) ]; then
    VERDICT="NEEDS ATTENTION"
else
    VERDICT="UNSTABLE"
fi

# Generate report
REPORT="process-v2.sh Test Report
Period: $START_DATE -> $END_DATE ($DAYS days)

Runs: $RUNS
  Full success: $FULL_SUCCESS
  Partial (fallback): $PARTIAL
  Skipped (empty daily): $SKIPPED

Phase Success Rates:
$(phase_stats "ORIENT")$(phase_stats "CAPTURE")$(phase_stats "EXECUTE")$(phase_stats "REFLECT")$(phase_stats "POST")$(phase_stats "GIT")$(phase_stats "TELEGRAM")
$TIMING_LINE

$([ -n "$ERRORS" ] && echo "Errors:" && echo "$ERRORS" || echo "Errors: none")

Verdict: $VERDICT"

echo "$REPORT"

# Send to Telegram if requested
if [ "$SEND_TELEGRAM" = true ]; then
    if [ -f "$ENV_FILE" ]; then
        export $(grep -v '^#' "$ENV_FILE" | xargs)
    fi
    CHAT_ID="${ALLOWED_USER_IDS//[\[\]]/}"
    if [ -n "${TELEGRAM_BOT_TOKEN:-}" ] && [ -n "$CHAT_ID" ]; then
        curl -s -X POST "https://api.telegram.org/bot$TELEGRAM_BOT_TOKEN/sendMessage" \
            -d "chat_id=$CHAT_ID" \
            -d "text=<pre>$REPORT</pre>" \
            -d "parse_mode=HTML" > /dev/null
        echo ""
        echo "(Sent to Telegram)"
    fi
fi

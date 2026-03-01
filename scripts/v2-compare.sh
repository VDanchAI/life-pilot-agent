#!/bin/bash
# v2-compare.sh — Compare v1 and v2 processing results for a given day
# Usage: bash scripts/v2-compare.sh [YYYY-MM-DD]

DATE=${1:-$(date +%Y-%m-%d)}
PROJECT_DIR="${PROJECT_DIR:-$(cd "$(dirname "$0")/.." && pwd)}"
V1_LOG="/var/log/d-brain-cron.log"
V2_LOG="$PROJECT_DIR/logs/process-v2.log"

echo "Comparison for $DATE"
echo "=========================="

# v1 data
echo ""
echo "--- v1 (process.sh) ---"
if [ -f "$V1_LOG" ]; then
    V1_LINES=$(grep "$DATE" "$V1_LOG" 2>/dev/null | wc -l)
    V1_DONE=$(grep "$DATE" "$V1_LOG" 2>/dev/null | grep -c "Done" || echo "0")
    V1_ERRORS=$(grep "$DATE" "$V1_LOG" 2>/dev/null | grep -ci "error\|fail" || echo "0")
    echo "  Log lines: $V1_LINES"
    echo "  Completed: $V1_DONE"
    echo "  Errors:    $V1_ERRORS"

    # Check git log for v1 commit
    V1_COMMIT=$(cd "$PROJECT_DIR" && git log --oneline --after="$DATE 00:00" --before="$DATE 23:59" --grep="process daily $DATE" 2>/dev/null | head -1)
    echo "  Commit:    ${V1_COMMIT:-none}"
else
    echo "  No v1 log found at $V1_LOG"
fi

# v2 data
echo ""
echo "--- v2 (process-v2.sh) ---"
if [ -f "$V2_LOG" ]; then
    V2_START=$(grep "$DATE" "$V2_LOG" | grep "| START " | head -1)
    V2_END=$(grep "$DATE" "$V2_LOG" | grep "| END " | head -1)

    if [ -n "$V2_START" ]; then
        echo "  Started:   $(echo "$V2_START" | awk '{print $1, $2}')"

        # Phase results
        for PHASE in ORIENT CAPTURE EXECUTE REFLECT POST GIT TELEGRAM; do
            LINE=$(grep "$DATE" "$V2_LOG" | grep "| $PHASE " | tail -1)
            if [ -n "$LINE" ]; then
                STATUS=$(echo "$LINE" | awk -F'|' '{gsub(/^ +| +$/,"",$3); print $3}')
                DURATION=$(echo "$LINE" | awk -F'|' '{gsub(/^ +| +$/,"",$4); print $4}')
                printf "  %-10s %s (%s)\n" "$PHASE:" "$STATUS" "$DURATION"
            fi
        done

        if [ -n "$V2_END" ]; then
            TOTAL=$(echo "$V2_END" | grep -oP '\d+s' | head -1)
            PHASES=$(echo "$V2_END" | grep -oP 'phases=\S+')
            echo "  Total:     $TOTAL ($PHASES)"
        fi
    else
        echo "  No v2 run found for $DATE"
    fi

    # Check session files
    echo ""
    echo "--- Session files ---"
    for F in capture.json execute.json; do
        FPATH="$PROJECT_DIR/vault/.session/$F"
        if [ -f "$FPATH" ]; then
            SIZE=$(wc -c < "$FPATH")
            HAS_ERROR=$(grep -c '"error"' "$FPATH" 2>/dev/null || echo "0")
            echo "  $F: ${SIZE}b $([ "$HAS_ERROR" -gt 0 ] && echo '[HAS ERRORS]' || echo '[OK]')"
        else
            echo "  $F: not found"
        fi
    done
else
    echo "  No v2 log found at $V2_LOG"
fi

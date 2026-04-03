#!/usr/bin/env bash
set -euo pipefail

cd ~/Projects/BitGN
mkdir -p /tmp/pcdred-cycles docs/run_logs

PROMPT="$(cat docs/superpowers/plans/pcdred-cycle-prompt.txt)"
CYCLES=${1:-20}
COOLDOWN=${2:-60}
NEUTRAL_STREAK=0

echo "=== PCDRED Loop: $CYCLES cycles, ${COOLDOWN}s cooldown ==="
echo "Backend: $(grep LLM_BACKEND pac1-py/.env | head -1)"
echo "Model:   $(grep MODEL_ID pac1-py/.env | head -1)"
echo ""

for i in $(seq 1 "$CYCLES"); do
  echo ""
  echo "=== Cycle $i/$CYCLES — $(date -u '+%Y-%m-%d %H:%M UTC') ==="
  LOG="/tmp/pcdred-cycles/cycle-${i}-$(date -u +%Y%m%d-%H%M).log"

  claude --model claude-opus-4-6 \
         --permission-mode acceptEdits \
         --max-turns 50 \
         -p "$PROMPT" \
         2>&1 | tee "$LOG"

  echo ""
  echo "Cycle $i done. Log: $LOG"

  # Print latest score from run_history.json
  python3 -c "
import json, pathlib
h = json.loads(pathlib.Path('docs/run_history.json').read_text())
if h:
    r = h[-1]
    print(f\"  Score: {r['tasks_passed']}/{r['tasks_total']} ({r['score_pct']}%) — {r.get('model','?')}\")
" 2>/dev/null || true

  # Check for early-stop: 3 consecutive NEUTRAL/REGRESSED
  LATEST_EVAL=$(ls -t docs/eval/run-*.md 2>/dev/null | head -1)
  if [ -n "$LATEST_EVAL" ]; then
    if grep -q "Delta: +0.0pp\|Delta: -" "$LATEST_EVAL" 2>/dev/null; then
      NEUTRAL_STREAK=$((NEUTRAL_STREAK + 1))
      echo "  Neutral/regressed streak: $NEUTRAL_STREAK"
    else
      NEUTRAL_STREAK=0
    fi
  fi

  if [ "$NEUTRAL_STREAK" -ge 3 ]; then
    echo ""
    echo "=== EARLY STOP: 3 consecutive neutral/regressed cycles ==="
    break
  fi

  if [ "$i" -lt "$CYCLES" ]; then
    echo "Cooldown ${COOLDOWN}s..."
    sleep "$COOLDOWN"
  fi
done

echo ""
echo "=== ALL CYCLES COMPLETE — $(date -u '+%Y-%m-%d %H:%M UTC') ==="

# Final summary
python3 -c "
import json, pathlib
h = json.loads(pathlib.Path('docs/run_history.json').read_text())
if len(h) >= 2:
    first, last = h[-min(len(h), $CYCLES)], h[-1]
    print(f\"Start: {first['score_pct']}% → End: {last['score_pct']}% (delta: {last['score_pct']-first['score_pct']:+.1f}pp)\")
" 2>/dev/null || true

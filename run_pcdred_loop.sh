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

  # Recompile wiki and show current score
  python3 compile_wiki.py 2>/dev/null || true
  head -9 docs/wiki/index.md 2>/dev/null | tail -4 || true

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

# Final wiki compile and summary
python3 compile_wiki.py 2>/dev/null || true
echo "Final wiki state:"
head -12 docs/wiki/index.md 2>/dev/null | grep -E "^\- " || true

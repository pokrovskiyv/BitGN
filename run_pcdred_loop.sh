#!/usr/bin/env bash
set -euo pipefail

cd ~/Projects/BitGN
mkdir -p /tmp/pcdred-cycles

PROMPT="$(cat docs/superpowers/plans/pcdred-cycle-prompt.txt)"

for i in $(seq 1 10); do
  echo ""
  echo "=== Cycle $i/10 — $(date -u '+%Y-%m-%d %H:%M UTC') ==="
  LOG="/tmp/pcdred-cycles/cycle-${i}-$(date -u +%Y%m%d-%H%M).log"

  claude --model claude-sonnet-4-6 \
         --permission-mode bypassPermissions \
         --max-turns 50 \
         -p "$PROMPT" \
         2>&1 | tee "$LOG"

  echo ""
  echo "Cycle $i done. Log: $LOG"

  if [ "$i" -lt 10 ]; then
    echo "Cooldown 30s..."
    sleep 30
  fi
done

echo ""
echo "=== ALL 10 CYCLES COMPLETE — $(date -u '+%Y-%m-%d %H:%M UTC') ==="

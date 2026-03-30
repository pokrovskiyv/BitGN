#!/usr/bin/env bash
set -euo pipefail

CYCLES="${1:-10}"
COOLDOWN="${2:-30}"
PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROMPT_FILE="$PROJECT_DIR/docs/superpowers/plans/pcdred-cycle-prompt.txt"
LOG_DIR="/tmp/pcdred-cycles"

mkdir -p "$LOG_DIR"

echo "PCDRED Auto-Cycles: $CYCLES cycles, ${COOLDOWN}s cooldown"
echo "Project: $PROJECT_DIR"
echo "Logs: $LOG_DIR"
echo ""

for i in $(seq 1 "$CYCLES"); do
  TIMESTAMP=$(date -u +%Y-%m-%d-%H%M)
  LOG_FILE="$LOG_DIR/cycle-${i}-${TIMESTAMP}.log"

  echo "========================================"
  echo "  Cycle $i/$CYCLES — $TIMESTAMP UTC"
  echo "========================================"

  claude \
    --model claude-sonnet-4-6 \
    --permission-mode acceptEdits \
    --max-turns 50 \
    -p "$(cat "$PROMPT_FILE")" \
    2>&1 | tee "$LOG_FILE"

  echo ""
  echo "Cycle $i complete. Log: $LOG_FILE"

  if [ "$i" -lt "$CYCLES" ]; then
    echo "Cooldown ${COOLDOWN}s..."
    sleep "$COOLDOWN"
  fi
done

echo ""
echo "========================================"
echo "  All $CYCLES cycles complete"
echo "========================================"
echo "Logs in: $LOG_DIR"

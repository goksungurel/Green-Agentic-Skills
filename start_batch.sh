#!/bin/bash
# Starts the full batch experiment (30 tasks x 2 conditions x 5 runs = 300 runs, max_steps=15).
# WARNING: --fresh archives existing runs.csv — only use for a clean start.
# - caffeinate: prevents macOS sleep
# - nohup: keeps process alive if terminal is closed
# - logs go to results/batch_run.log

cd "$(dirname "$0")"
source venv/bin/activate
export MSWEA_COST_TRACKING='ignore_errors'

LOG="results/batch_run.log"
mkdir -p results

echo "Starting batch at $(date)" | tee "$LOG"
echo "Logs → $LOG"
echo "Monitor with: tail -f $LOG"
echo "To stop:      kill \$(cat results/batch.pid)"
echo ""

nohup caffeinate -i venv/bin/python3 run_batch.py --fresh >> "$LOG" 2>&1 &
PID=$!
echo $PID > results/batch.pid
echo "PID: $PID — saved to results/batch.pid"

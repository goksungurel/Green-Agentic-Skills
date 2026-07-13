#!/bin/bash
# Runs the SWE-bench harness (Docker) on any not-yet-evaluated patches in
# results/patches/ -> results/accuracy.csv (main pipeline).
# Resumable: automatically skips (task_id, condition, run) already present
# in results/accuracy.csv, so this is safe to re-run any time.
# - caffeinate: prevents macOS sleep while left unattended
# - nohup: keeps process alive if terminal is closed
# - logs go to results/evaluate_run.log

cd "$(dirname "$0")"
source venv/bin/activate

LOG="results/evaluate_run.log"
mkdir -p results

echo "Starting harness evaluation at $(date)" | tee "$LOG"
echo "Logs → $LOG"
echo "Monitor with: tail -f $LOG"
echo "To stop:      kill \$(cat results/evaluate.pid)"
echo ""

nohup caffeinate -i venv/bin/python3 evaluate_patches.py >> "$LOG" 2>&1 &
PID=$!
echo $PID > results/evaluate.pid
echo "PID: $PID — saved to results/evaluate.pid"

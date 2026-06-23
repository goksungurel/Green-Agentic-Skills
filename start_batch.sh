#!/bin/bash
# Starts the full batch experiment (30 tasks x 2 conditions x 3 runs = 180 runs).
# - pmset: prevents macOS from sleeping even with lid closed (charger required)
# - caffeinate: additional sleep prevention
# - nohup: keeps process alive if terminal is closed
# - logs go to results/batch_run.log

cd "$(dirname "$0")"
source venv/bin/activate
export MSWEA_COST_TRACKING='ignore_errors'

LOG="results/batch_run.log"
mkdir -p results

# Prevent sleep even with lid closed (requires charger)
echo "Disabling sleep while on AC power (requires sudo)..."
sudo pmset -c sleep 0

echo "Starting batch at $(date)" | tee "$LOG"
echo "Logs → $LOG"
echo "Monitor with: tail -f $LOG"
echo "To stop:      kill \$(cat results/batch.pid)"
echo ""

nohup caffeinate -is venv/bin/python3 run_batch.py --fresh >> "$LOG" 2>&1 &
PID=$!
echo $PID > results/batch.pid
echo "PID: $PID — saved to results/batch.pid"

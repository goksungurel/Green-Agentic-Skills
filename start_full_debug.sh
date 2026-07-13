#!/bin/bash
# Starts the full systematic-debugging skill pilot (30 tasks x 2 conditions x 5 runs = 300 runs).
# Separate from the main experiment — writes only to results/runs_full_debug.csv,
# results/trajectories_full_debug/, results/patches_full_debug/.
# - caffeinate: prevents macOS sleep while the Mac is left unattended
# - nohup: keeps the process alive if the terminal is closed
# - logs go to results/full_debug_run.log

cd "$(dirname "$0")"
source venv/bin/activate
export MSWEA_COST_TRACKING='ignore_errors'

LOG="results/full_debug_run.log"
mkdir -p results

echo "Starting full-debug pilot at $(date)" | tee "$LOG"
echo "Logs → $LOG"
echo "Monitor with: tail -f $LOG"
echo "To stop:      kill \$(cat results/full_debug.pid)"
echo ""

nohup caffeinate -i venv/bin/python3 run_full_debug_pilot.py >> "$LOG" 2>&1 &
PID=$!
echo $PID > results/full_debug.pid
echo "PID: $PID — saved to results/full_debug.pid"

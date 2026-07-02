#!/bin/bash
# Runs validate_dedup_fix.py: 3 (task, condition) pairs x 2 runs = 6 runs,
# on the exact pairs whose round-2 LimitsExceeded runs were confirmed (via
# direct trajectory inspection) to be 100% wasted by the model repeating one
# byte-identical command for the entire step budget.
#
# - caffeinate: prevents macOS sleep
# - nohup: keeps process alive if terminal is closed
# - logs go to results/validation_run_dedup.log
#
# Close background tabs/apps before running this for clean energy measurement.

cd "$(dirname "$0")"
source venv/bin/activate
export MSWEA_COST_TRACKING='ignore_errors'

LOG="results/validation_run_dedup.log"
mkdir -p results

echo "Starting dedup-guard validation at $(date)" | tee "$LOG"
echo "Logs   -> $LOG"
echo "Monitor with: tail -f $LOG"
echo "To stop:      kill \$(cat results/validation_dedup.pid)"
echo ""

nohup caffeinate -i venv/bin/python3 validate_dedup_fix.py >> "$LOG" 2>&1 &
PID=$!
echo $PID > results/validation_dedup.pid
echo "PID: $PID -- saved to results/validation_dedup.pid"

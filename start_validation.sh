#!/bin/bash
# Runs validate_blueprint_fix.py: 5 (task, condition) pairs x 2 runs = 10 runs,
# to check whether the mini.yaml literal-placeholder fix (class Blueprint /
# def method_name) actually stops the copy-paste bug on the exact tasks that
# were 100% wasted by it before (django-11039, xarray-3364, requests-2317).
#
# - caffeinate: prevents macOS sleep
# - nohup: keeps process alive if terminal is closed
# - logs go to results/validation_run.log
#
# Close background tabs/apps before running this for clean energy measurement.

cd "$(dirname "$0")"
source venv/bin/activate
export MSWEA_COST_TRACKING='ignore_errors'

LOG="results/validation_run.log"
mkdir -p results

echo "Starting validation at $(date)" | tee "$LOG"
echo "Logs   → $LOG"
echo "Monitor with: tail -f $LOG"
echo "To stop:      kill \$(cat results/validation.pid)"
echo ""

nohup caffeinate -i venv/bin/python3 validate_blueprint_fix.py >> "$LOG" 2>&1 &
PID=$!
echo $PID > results/validation.pid
echo "PID: $PID — saved to results/validation.pid"

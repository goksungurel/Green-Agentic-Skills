#!/bin/bash
# Runs validate_fixes_v2.py: 5 (task, condition) pairs x 2 runs = 10 runs,
# to check whether the 3 fixes applied after round-1 validation actually work:
#   1. FOUND_FILE_PATH placeholder fix (was /path/to/file.py)
#   2. sed `\n`-in-replacement footgun warning
#   3. sed -i removed entirely (python3 .replace() required for all edits)
#
# - caffeinate: prevents macOS sleep
# - nohup: keeps process alive if terminal is closed
# - logs go to results/validation_run_v2.log
#
# Close background tabs/apps before running this for clean energy measurement.

cd "$(dirname "$0")"
source venv/bin/activate
export MSWEA_COST_TRACKING='ignore_errors'

LOG="results/validation_run_v2.log"
mkdir -p results

echo "Starting validation v2 at $(date)" | tee "$LOG"
echo "Logs   → $LOG"
echo "Monitor with: tail -f $LOG"
echo "To stop:      kill \$(cat results/validation_v2.pid)"
echo ""

nohup caffeinate -i venv/bin/python3 validate_fixes_v2.py >> "$LOG" 2>&1 &
PID=$!
echo $PID > results/validation_v2.pid
echo "PID: $PID — saved to results/validation_v2.pid"

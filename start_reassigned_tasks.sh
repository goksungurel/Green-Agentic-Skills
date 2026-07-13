#!/bin/bash
# Backfills the 3 tasks reassigned from logic_debug/feature to exception_debug
# (mwaskom__seaborn-2848, mwaskom__seaborn-3407, astropy__astropy-14365).
#
# Their baseline runs already exist in results/runs.csv (5/5 each, unaffected
# by the category change) and will be skipped automatically. Only their
# task_specific_skill condition is missing under the NEW category
# (exception_debug_skill) — this adds exactly those 15 runs (3 tasks x 5).
#
# Does NOT use --fresh — does not touch or archive the existing 285 rows.
# - caffeinate: prevents macOS sleep
# - nohup: keeps process alive if terminal is closed
# - logs go to results/reassigned_run.log

cd "$(dirname "$0")"
source venv/bin/activate
export MSWEA_COST_TRACKING='ignore_errors'

LOG="results/reassigned_run.log"
mkdir -p results

echo "Starting reassigned-task backfill at $(date)" | tee "$LOG"
echo "Logs → $LOG"
echo "Monitor with: tail -f $LOG"
echo "To stop:      kill \$(cat results/reassigned.pid)"
echo ""

nohup caffeinate -i venv/bin/python3 run_batch.py --only \
    mwaskom__seaborn-2848 mwaskom__seaborn-3407 astropy__astropy-14365 \
    >> "$LOG" 2>&1 &
PID=$!
echo $PID > results/reassigned.pid
echo "PID: $PID — saved to results/reassigned.pid"

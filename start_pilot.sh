#!/bin/bash
# Pilot run: 20 tasks (balanced across 3 types) x 2 conditions x 5 runs = 200 runs.
# Uses --fresh to archive any existing runs.csv and start clean.
# - caffeinate: prevents macOS sleep
# - nohup: keeps process alive if terminal is closed
# - logs go to results/pilot_run.log

cd "$(dirname "$0")"
source venv/bin/activate
export MSWEA_COST_TRACKING='ignore_errors'

LOG="results/pilot_run.log"
mkdir -p results

echo "Starting pilot at $(date)" | tee "$LOG"
echo "Logs → $LOG"
echo "Monitor with: tail -f $LOG"
echo "To stop:      kill \$(cat results/pilot.pid)"
echo ""

# 20 tasks: 4 exception_debug + 9 logic_debug + 7 feature
TASKS=(
    astropy__astropy-14995
    mwaskom__seaborn-3190
    matplotlib__matplotlib-22711
    psf__requests-2148
    django__django-11001
    astropy__astropy-6938
    django__django-11019
    django__django-11039
    psf__requests-1963
    psf__requests-2317
    mwaskom__seaborn-2848
    pydata__xarray-4094
    matplotlib__matplotlib-23299
    pallets__flask-4992
    astropy__astropy-14365
    django__django-10924
    astropy__astropy-14182
    matplotlib__matplotlib-18869
    pallets__flask-4045
    pydata__xarray-3364
)

nohup caffeinate -i venv/bin/python3 run_batch.py --fresh --only "${TASKS[@]}" \
    >> "$LOG" 2>&1 &
PID=$!
echo $PID > results/pilot.pid
echo "PID: $PID — saved to results/pilot.pid"

#!/bin/bash
# Resumes batch from where it left off (does NOT archive existing results).
# Use this after a crash, freeze, or manual stop.

cd "$(dirname "$0")"
source venv/bin/activate
export MSWEA_COST_TRACKING='ignore_errors'

LOG="results/batch_run.log"

sudo pmset -c sleep 0

echo "Resuming batch at $(date)" | tee -a "$LOG"

nohup caffeinate -is venv/bin/python3 run_batch.py >> "$LOG" 2>&1 &
PID=$!
echo $PID > results/batch.pid
echo "PID: $PID — Monitor: tail -f $LOG"

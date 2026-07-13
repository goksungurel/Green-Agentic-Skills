#!/bin/bash
# Starts the SWE-bench harness evaluation for the full-debug pilot's patches
# (results/patches_full_debug/ -> results/accuracy_full_debug.csv).
# This can take 20-35+ hours (83 patches, ~13-77 min each, sequential Docker runs).
# - caffeinate: prevents macOS sleep while left unattended
# - nohup: keeps process alive if terminal is closed
# - logs go to results/evaluate_full_debug_run.log

cd "$(dirname "$0")"
source venv/bin/activate

LOG="results/evaluate_full_debug_run.log"
mkdir -p results

echo "Starting full-debug harness evaluation at $(date)" | tee "$LOG"
echo "Logs → $LOG"
echo "Monitor with: tail -f $LOG"
echo "To stop:      kill \$(cat results/evaluate_full_debug.pid)"
echo ""

nohup caffeinate -i venv/bin/python3 evaluate_patches_full_debug.py >> "$LOG" 2>&1 &
PID=$!
echo $PID > results/evaluate_full_debug.pid
echo "PID: $PID — saved to results/evaluate_full_debug.pid"

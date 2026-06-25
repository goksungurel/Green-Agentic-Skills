#!/usr/bin/env bash
# Overnight run: 5-task mini-batch → harness → analyze
# macOS sleep prevention: caffeinate keeps the machine awake

set -e
cd "$(dirname "$0")"
source venv/bin/activate

# ── 5 selected tasks ──────────────────────────────────────────────────
TASKS=(
    psf__requests-2317      # logic_debug   : builtin_str method bug
    psf__requests-2148      # exception_debug: socket.error not wrapped
    mwaskom__seaborn-3010   # exception_debug: PolyFit + missing data
    pallets__flask-4992     # feature        : Config.from_file mode param
    django__django-10914    # feature        : FILE_UPLOAD_PERMISSIONS default
)

LOG="results/overnight_$(date +%Y%m%d_%H%M%S).log"
mkdir -p results

echo "========================================"
echo " GreenSkill Overnight Run"
echo " Tasks : ${#TASKS[@]}"
echo " N_RUNS: 5 per condition"
echo " Log   : $LOG"
echo " Start : $(date)"
echo "========================================"

# Prevent macOS sleep for entire run
caffeinate -i -w $$ &
CAFE_PID=$!
echo "caffeinate PID: $CAFE_PID (keeps machine awake)"

cleanup() {
    kill $CAFE_PID 2>/dev/null || true
    echo "caffeinate stopped."
}
trap cleanup EXIT

# ── Step 1: Batch runs ────────────────────────────────────────────────
echo ""
echo "STEP 1/3: Running batch..."
python3 run_batch.py --only "${TASKS[@]}" 2>&1 | tee "$LOG"

# ── Step 2: Harness evaluation ────────────────────────────────────────
echo ""
echo "STEP 2/3: Running SWE-bench harness on all patches..."
python3 evaluate_patches.py 2>&1 | tee -a "$LOG"

# ── Step 3: Analysis ──────────────────────────────────────────────────
echo ""
echo "STEP 3/3: Analyzing results..."
python3 analyze.py 2>&1 | tee -a "$LOG"

echo ""
echo "========================================"
echo " DONE: $(date)"
echo " Full log: $LOG"
echo "========================================"

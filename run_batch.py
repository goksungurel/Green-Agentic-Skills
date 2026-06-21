"""
run_batch.py
------------
3-condition experiment on 10 diverse tasks:

  baseline          — no skill
  general_skill     — skill.md (general guidance)
  task_specific_skill — debugging_skill.md for debug tasks
                        feature_skill.md   for feature tasks

Results appended to results/runs.csv.
"""

import csv
import experiment

N_RUNS = 3  # per condition (10 tasks x 3 conditions x 3 runs = 90 runs total)

# Each task tagged with type: "debug" or "feature"
BATCH = [
    # --- debug: TypeError / None / boolean ---
    {
        "id": "astropy__astropy-14995", "type": "debug",
        "problem": (
            "In v5.3, NDDataRef mask propagation fails when one of the operands does not "
            "have a mask. With handle_mask=np.bitwise_or, it raises: "
            "TypeError: unsupported operand type(s) for |: 'int' and 'NoneType'. "
            "Expected: the existing mask should just be copied when the other operand has no mask."
        ),
    },
    {
        "id": "mwaskom__seaborn-3190", "type": "debug",
        "problem": (
            "Color mapping fails with boolean data. "
            "so.Plot(['a','b'], [1,2], color=[True, False]).add(so.Bar()) raises: "
            "TypeError: numpy boolean subtract, the `-` operator, is not supported. "
            "Boolean color values should be treated as numeric."
        ),
    },
    {
        "id": "mwaskom__seaborn-3010", "type": "debug",
        "problem": (
            "PolyFit is not robust to missing data. "
            "so.Plot([1, 2, 3, None, 4], [1, 2, 3, 4, 5]).add(so.Line(), so.PolyFit()) "
            "raises LinAlgError: SVD did not converge in Linear Least Squares. "
            "None/NaN values should be dropped before fitting."
        ),
    },
    {
        "id": "matplotlib__matplotlib-22711", "type": "debug",
        "problem": (
            "RangeSlider widget cannot be given an initial value. "
            "RangeSlider(..., valinit=[0.0, 0.0]) raises: "
            "IndexError: index 4 is out of bounds for axis 0 with size 4. "
            "The polygon xy array only has 4 points but the code tries to set index 4."
        ),
    },
    {
        "id": "matplotlib__matplotlib-22835", "type": "debug",
        "problem": (
            "scalar mappable format_cursor_data crashes on BoundaryNorm. "
            "Mousing over an image with BoundaryNorm raises: "
            "ValueError: BoundaryNorm is not invertible. "
            "The crash should be caught and handled gracefully."
        ),
    },
    {
        "id": "django__django-11001", "type": "debug",
        "problem": (
            "Incorrect removal of order_by clause created as multiline RawSQL. "
            "SQLCompiler.get_order_by() uses a regex on multiline SQL, which returns only "
            "the last line. Identical last lines cause duplicate detection to wrongly remove "
            "distinct ORDER BY clauses. Fix: strip newlines from sql before the regex search."
        ),
    },
    {
        "id": "astropy__astropy-6938", "type": "debug",
        "problem": (
            "Possible bug in io.fits related to D exponents. "
            "In fitsrec.py: output_field.replace(encode_ascii('E'), encode_ascii('D')) "
            "does nothing because chararray.replace() is not in-place — it returns a copy "
            "that is discarded. The result should be assigned back."
        ),
    },
    # --- feature: add parameter / extend API ---
    {
        "id": "pallets__flask-4992", "type": "feature",
        "problem": (
            "Add a file mode parameter to flask.Config.from_file(). "
            "tomllib.load() requires binary mode but from_file() opens in text mode. "
            "Add a mode parameter (default 'r') so callers can pass mode='b' for binary loaders."
        ),
    },
    {
        "id": "astropy__astropy-14365", "type": "feature",
        "problem": (
            "ascii.qdp Table format assumes QDP commands are upper case. "
            "QDP itself is case-insensitive but astropy raises ValueError for lowercase commands "
            "like 'read serr 1 2'. The parser should handle commands case-insensitively."
        ),
    },
    {
        "id": "django__django-10924", "type": "feature",
        "problem": (
            "Allow FilePathField path to accept a callable. "
            "Currently path must be a string, which gets resolved at migration time. "
            "If path is callable, it should be called at runtime instead of at migration time."
        ),
    },
]

# task type → which specific skill file to use
SPECIFIC_SKILL = {
    "debug":   "debug_skill",
    "feature": "feature_skill",
}

CONDITIONS = ["baseline", "task_specific_skill"]


def load_existing_runs():
    done = set()
    try:
        with open(experiment.RESULTS_CSV, newline="") as f:
            for row in csv.DictReader(f):
                done.add((row["task_id"], row["condition"], row["run"]))
    except FileNotFoundError:
        pass
    return done


if __name__ == "__main__":
    experiment.ensure_results_dir()
    done = load_existing_runs()

    n_debug   = sum(1 for t in BATCH if t["type"] == "debug")
    n_feature = sum(1 for t in BATCH if t["type"] == "feature")

    print("=" * 70)
    print(f"Batch  : {len(BATCH)} tasks ({n_debug} debug, {n_feature} feature)")
    print(f"Conds  : {' | '.join(CONDITIONS)}")
    print(f"Runs   : {N_RUNS} per condition  →  {len(BATCH) * 3 * N_RUNS} total runs")
    print(f"Output : {experiment.RESULTS_CSV}")
    print("=" * 70)

    all_results = []

    for task in BATCH:
        task_id = task["id"]
        problem = task["problem"]
        task_type = task["type"]

        print(f"\n{'='*70}")
        print(f"TASK : {task_id}  [{task_type}]")
        print(f"{'='*70}")

        for cond_label in CONDITIONS:
            # Map "task_specific_skill" to the right internal condition key
            if cond_label == "task_specific_skill":
                condition = SPECIFIC_SKILL[task_type]
            else:
                condition = cond_label

            # Per-run resume: collect which run indices still need to run
            pending = [
                r for r in range(1, N_RUNS + 1)
                if (task_id, condition, str(r)) not in done
            ]
            if not pending:
                print(f"  [{cond_label}] already complete, skipping.")
                continue

            print(f"\n  Running [{condition}] — pending runs: {pending}")
            run_results = []
            for i in pending:
                print(f"    run {i}/{N_RUNS}...", end=" ", flush=True)
                r = experiment.run_once(task_id, problem, condition, run_index=i)
                run_results.append(r)
                experiment.append_result(r)
                done.add((task_id, condition, str(i)))
                print(f"energy={r['energy_kwh']:.8f} kWh  "
                      f"duration={r['duration_s']:.1f}s  success={r['success']}")

            valid = [r for r in run_results if r["success"] and r["emissions_kg"] > 0]
            avg = lambda key: sum(r[key] for r in valid) / len(valid) if valid else 0.0
            print(f"  --> avg energy   : {avg('energy_kwh'):.8f} kWh")
            print(f"  --> avg duration : {avg('duration_s'):.1f} s")
            print(f"  --> success rate : {len([r for r in run_results if r['success']])}/{len(pending)}")

            all_results.append({
                "task_id":       task_id,
                "condition":     condition,
                "condition_label": cond_label,
                "avg_energy":    avg("energy_kwh"),
                "avg_emissions": avg("emissions_kg"),
                "avg_duration":  avg("duration_s"),
                "n_valid":       len(valid),
            })

    # ── Summary table ──────────────────────────────────────────────────
    print("\n" + "=" * 70)
    print("BATCH SUMMARY  (avg energy kWh per condition)")
    print("=" * 70)
    print(f"{'Task':<38} {'baseline':>10} {'general':>10} {'specific':>10} {'best':>8}")
    print("-" * 70)

    def get_avg(task_id, cond_label):
        for r in all_results:
            if r["task_id"] == task_id and r.get("condition_label", r["condition"]) == cond_label:
                return r["avg_energy"]
        return None

    for task in BATCH:
        tid = task["id"]
        short = tid.split("__")[1][:35]
        b = get_avg(tid, "baseline")
        g = get_avg(tid, "general_skill")
        s = get_avg(tid, "task_specific_skill")
        vals = {k: v for k, v in [("baseline", b), ("general", g), ("specific", s)] if v}
        best = min(vals, key=vals.get) if vals else "?"
        fmt = lambda v: f"{v:.6f}" if v else "   n/a  "
        print(f"{short:<38} {fmt(b):>10} {fmt(g):>10} {fmt(s):>10} {best:>8}")

    print(f"\nAll results saved to: {experiment.RESULTS_CSV}")
    print("=" * 70)

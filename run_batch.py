"""
run_batch.py
------------
2-condition experiment on 30 tasks:

  baseline            — no skill
  task_specific_skill — exception_debug_skill.md for exception bugs
                        logic_debug_skill.md     for silent/logic bugs
                        feature_skill.md         for feature tasks

30 tasks x 2 conditions x 5 runs = 300 total runs.
Results appended to results/runs.csv.
"""

import argparse
import csv
import os
import shutil
from datetime import datetime

import experiment

N_RUNS = 5

# Each task tagged with type only — problem_statement loaded from selected_tasks.csv at runtime
BATCH = [
    # --- exception_debug: bugs with a clear exception / traceback ---
    {"id": "astropy__astropy-14995",    "type": "exception_debug"},
    {"id": "mwaskom__seaborn-3190",     "type": "exception_debug"},
    {"id": "mwaskom__seaborn-3010",     "type": "exception_debug"},
    {"id": "matplotlib__matplotlib-22711", "type": "exception_debug"},
    {"id": "matplotlib__matplotlib-22835", "type": "exception_debug"},
    {"id": "psf__requests-2148",        "type": "exception_debug"},
    {"id": "psf__requests-2674",        "type": "exception_debug"},
    # --- logic_debug: silent / wrong-result bugs, no exception ---
    {"id": "django__django-11001",      "type": "logic_debug"},
    {"id": "astropy__astropy-6938",     "type": "logic_debug"},
    {"id": "django__django-11019",      "type": "logic_debug"},
    {"id": "django__django-11039",      "type": "logic_debug"},
    {"id": "astropy__astropy-12907",    "type": "logic_debug"},
    {"id": "matplotlib__matplotlib-23299", "type": "logic_debug"},
    {"id": "matplotlib__matplotlib-23314", "type": "logic_debug"},
    {"id": "psf__requests-1963",        "type": "logic_debug"},
    {"id": "psf__requests-2317",        "type": "logic_debug"},
    {"id": "psf__requests-3362",        "type": "logic_debug"},
    {"id": "mwaskom__seaborn-2848",     "type": "logic_debug"},
    {"id": "mwaskom__seaborn-3407",     "type": "logic_debug"},
    {"id": "pydata__xarray-4094",       "type": "logic_debug"},
    # --- feature: add parameter / extend API ---
    {"id": "pallets__flask-4992",       "type": "feature"},
    {"id": "astropy__astropy-14365",    "type": "feature"},
    {"id": "django__django-10924",      "type": "feature"},
    {"id": "django__django-10914",      "type": "feature"},
    {"id": "astropy__astropy-14182",    "type": "feature"},
    {"id": "matplotlib__matplotlib-18869", "type": "feature"},
    {"id": "pallets__flask-4045",       "type": "feature"},
    {"id": "pallets__flask-5063",       "type": "feature"},
    {"id": "pydata__xarray-3364",       "type": "feature"},
    {"id": "pydata__xarray-4248",       "type": "feature"},
]

# task type → which specific skill file to use
SPECIFIC_SKILL = {
    "exception_debug": "exception_debug_skill",
    "logic_debug":     "logic_debug_skill",
    "feature":         "feature_skill",
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


def archive_csv():
    """Move runs.csv to a timestamped backup so we start fresh."""
    csv_path = experiment.RESULTS_CSV
    if os.path.exists(csv_path):
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup = csv_path.replace(".csv", f"_archived_{ts}.csv")
        shutil.move(csv_path, backup)
        print(f"  Archived old results → {backup}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--fresh", action="store_true",
        help="Archive old runs.csv and start all runs from scratch"
    )
    parser.add_argument(
        "--only", nargs="+", metavar="TASK_ID",
        help="Run only these task IDs (space-separated)"
    )
    args = parser.parse_args()

    experiment.ensure_results_dir()

    if args.fresh:
        print("Fresh start: archiving old results...")
        archive_csv()
        experiment.ensure_results_dir()

    done = load_existing_runs()

    active_batch = BATCH
    if args.only:
        active_batch = [t for t in BATCH if t["id"] in args.only]
        if not active_batch:
            print(f"ERROR: no tasks matched {args.only}")
            raise SystemExit(1)

    n_exc     = sum(1 for t in active_batch if t["type"] == "exception_debug")
    n_logic   = sum(1 for t in active_batch if t["type"] == "logic_debug")
    n_feature = sum(1 for t in active_batch if t["type"] == "feature")

    print("=" * 70)
    print(f"Batch  : {len(active_batch)} tasks ({n_exc} exception_debug, {n_logic} logic_debug, {n_feature} feature)")
    print(f"Conds  : {' | '.join(CONDITIONS)}")
    print(f"Runs   : {N_RUNS} per condition  →  {len(active_batch) * 2 * N_RUNS} total runs")
    print(f"Output : {experiment.RESULTS_CSV}")
    print("=" * 70)

    all_results = []

    for task in active_batch:
        task_id   = task["id"]
        task_type = task["type"]

        # Load original problem statement from selected_tasks.csv (no hints)
        meta    = experiment.get_task_meta(task_id)
        problem = meta.get("problem_statement", "")
        if not problem:
            print(f"  [ERROR] No problem_statement found for {task_id} in selected_tasks.csv — skipping.")
            continue

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
                      f"duration={r['duration_s']:.1f}s  changed={r['code_changed']}")

            measured = [r for r in run_results if r["energy_kwh"] > 0]
            avg = lambda key: sum(r[key] for r in measured) / len(measured) if measured else 0.0
            print(f"  --> avg energy   : {avg('energy_kwh'):.8f} kWh")
            print(f"  --> avg duration : {avg('duration_s'):.1f} s")
            print(f"  --> code_changed : {sum(r['code_changed'] for r in run_results)}/{len(pending)}")
            print(f"  --> (accuracy via evaluate_patches.py + harness)")

            all_results.append({
                "task_id":         task_id,
                "condition":       condition,
                "condition_label": cond_label,
                "avg_energy":      avg("energy_kwh"),
                "avg_emissions":   avg("emissions_kg"),
                "avg_duration":    avg("duration_s"),
                "n_valid":         len(measured),
            })

    # ── Summary table ──────────────────────────────────────────────────
    print("\n" + "=" * 70)
    print("BATCH SUMMARY  (avg energy kWh per condition)")
    print("=" * 70)

    def get_avg(tid, cond):
        for r in all_results:
            if r["task_id"] == tid and r["condition"] == cond:
                return r["avg_energy"]
        return None

    fmt = lambda v: f"{v:.8f}" if v else "     n/a"

    baseline_vals = []
    skill_vals    = []

    for task in active_batch:
        tid   = task["id"]
        ttype = task["type"]
        skill_cond = SPECIFIC_SKILL[ttype]
        b = get_avg(tid, "baseline")
        s = get_avg(tid, skill_cond)
        best = ""
        if b is not None and s is not None:
            best = "← skill" if s < b else "← baseline"
            if b > 0: baseline_vals.append(b)
            if s > 0: skill_vals.append(s)
        short = tid.split("__")[1] if "__" in tid else tid
        print(f"  {short:<28} baseline={fmt(b)}   skill={fmt(s)}  {best}")

    if baseline_vals and skill_vals:
        avg_b = sum(baseline_vals) / len(baseline_vals)
        avg_s = sum(skill_vals)    / len(skill_vals)
        print("-" * 70)
        print(f"  {'AVERAGE':<28} baseline={avg_b:.8f}   skill={avg_s:.8f}")

    print("=" * 70)
    print(f"\nAll results saved to: {experiment.RESULTS_CSV}")
    print("=" * 70)

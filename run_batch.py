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

N_RUNS = 5  # per condition (30 tasks x 2 conditions x 5 runs = 300 runs total)

# Each task tagged with type: "exception_debug", "logic_debug", or "feature"
BATCH = [
    # --- exception_debug: bugs with a clear exception / traceback ---
    {
        "id": "astropy__astropy-14995", "type": "exception_debug",
        "problem": (
            "In v5.3, NDDataRef mask propagation fails when one of the operands does not "
            "have a mask. With handle_mask=np.bitwise_or, it raises: "
            "TypeError: unsupported operand type(s) for |: 'int' and 'NoneType'. "
            "Expected: the existing mask should just be copied when the other operand has no mask."
        ),
    },
    {
        "id": "mwaskom__seaborn-3190", "type": "exception_debug",
        "problem": (
            "Color mapping fails with boolean data. "
            "so.Plot(['a','b'], [1,2], color=[True, False]).add(so.Bar()) raises: "
            "TypeError: numpy boolean subtract, the `-` operator, is not supported. "
            "Boolean color values should be treated as numeric."
        ),
    },
    {
        "id": "mwaskom__seaborn-3010", "type": "exception_debug",
        "problem": (
            "PolyFit is not robust to missing data. "
            "so.Plot([1, 2, 3, None, 4], [1, 2, 3, 4, 5]).add(so.Line(), so.PolyFit()) "
            "raises LinAlgError: SVD did not converge in Linear Least Squares. "
            "None/NaN values should be dropped before fitting."
        ),
    },
    {
        "id": "matplotlib__matplotlib-22711", "type": "exception_debug",
        "problem": (
            "RangeSlider widget cannot be given an initial value. "
            "RangeSlider(..., valinit=[0.0, 0.0]) raises: "
            "IndexError: index 4 is out of bounds for axis 0 with size 4. "
            "The polygon xy array only has 4 points but the code tries to set index 4."
        ),
    },
    {
        "id": "matplotlib__matplotlib-22835", "type": "exception_debug",
        "problem": (
            "scalar mappable format_cursor_data crashes on BoundaryNorm. "
            "Mousing over an image with BoundaryNorm raises: "
            "ValueError: BoundaryNorm is not invertible. "
            "The crash should be caught and handled gracefully."
        ),
    },
    {
        "id": "django__django-11001", "type": "logic_debug",
        "problem": (
            "Incorrect removal of order_by clause created as multiline RawSQL. "
            "SQLCompiler.get_order_by() uses a regex on multiline SQL, which returns only "
            "the last line. Identical last lines cause duplicate detection to wrongly remove "
            "distinct ORDER BY clauses. Fix: strip newlines from sql before the regex search."
        ),
    },
    {
        "id": "astropy__astropy-6938", "type": "logic_debug",
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
    # --- remaining 20 tasks ---
    {
        "id": "django__django-10914", "type": "feature",
        "problem": (
            "Set default FILE_UPLOAD_PERMISSION to 0o644. "
            "FileSystemStorage._save() does not set file permissions, leaving them OS-dependent. "
            "Add a FILE_UPLOAD_PERMISSIONS setting defaulting to 0o644 and apply it after saving."
        ),
    },
    {
        "id": "django__django-11019", "type": "logic_debug",
        "problem": (
            "Merging 3 or more media objects throws unnecessary MediaOrderConflictWarnings. "
            "When merging CSS/JS lists from 3+ Media objects, the merge algorithm raises "
            "MediaOrderConflictWarning even when the ordering is consistent. "
            "Fix the merge so warnings only appear for genuine order conflicts."
        ),
    },
    {
        "id": "django__django-11039", "type": "logic_debug",
        "problem": (
            "sqlmigrate wraps output in BEGIN/COMMIT even if the database doesn't support "
            "transactional DDL. For databases like MySQL that don't support transactional DDL, "
            "the BEGIN/COMMIT should be omitted. Check connection.features.can_rollback_ddl."
        ),
    },
    {
        "id": "astropy__astropy-12907", "type": "logic_debug",
        "problem": (
            "Modeling's separability_matrix does not compute separability correctly for nested "
            "CompoundModels. When models are composed with &, the separability_matrix returns "
            "wrong results. The _separability function does not handle nested compound models correctly."
        ),
    },
    {
        "id": "astropy__astropy-14182", "type": "feature",
        "problem": (
            "Please support header rows in RestructuredText table output. "
            "The RST writer should accept a header_rows parameter (like the CSV writer does) "
            "to designate which rows are header rows and format them above the RST divider line."
        ),
    },
    {
        "id": "matplotlib__matplotlib-18869", "type": "feature",
        "problem": (
            "Add easily comparable version info to matplotlib toplevel. "
            "Add a __version_info__ tuple (e.g. (3, 5, 0)) alongside __version__ string "
            "so users can do version comparisons like matplotlib.__version_info__ >= (3, 4, 0)."
        ),
    },
    {
        "id": "matplotlib__matplotlib-23299", "type": "logic_debug",
        "problem": (
            "get_backend() clears figures from Gcf.figs if figures were created under rc_context. "
            "After using rc_context(), calling get_backend() unexpectedly removes all figures "
            "from the figure manager. The backend check should not affect stored figures."
        ),
    },
    {
        "id": "matplotlib__matplotlib-23314", "type": "logic_debug",
        "problem": (
            "set_visible() not working for 3D projection axes. "
            "Calling ax.set_visible(False) on a 3D subplot does not hide it — the axes remain "
            "visible. The Axes3D.set_visible() method needs to propagate to the underlying artists."
        ),
    },
    {
        "id": "psf__requests-1963", "type": "logic_debug",
        "problem": (
            "Session.resolve_redirects copies the original request for all redirect hops, "
            "causing incorrect behavior when a redirect changes the method (e.g. POST→GET). "
            "Each hop should copy the previous hop's request, not the original."
        ),
    },
    {
        "id": "psf__requests-2148", "type": "exception_debug",
        "problem": (
            "socket.error exceptions are not caught or wrapped in a requests exception. "
            "A raw socket.error can propagate to the caller instead of being wrapped as "
            "requests.exceptions.ConnectionError. Catch socket.error alongside other low-level errors."
        ),
    },
    {
        "id": "psf__requests-2317", "type": "logic_debug",
        "problem": (
            "In requests/sessions.py, `method = builtin_str(method)` converts the HTTP method "
            "to bytes on Python 2 but causes issues. Replace builtin_str with str.upper() "
            "so the method is always a native string in uppercase."
        ),
    },
    {
        "id": "psf__requests-2674", "type": "exception_debug",
        "problem": (
            "urllib3 exceptions (DecodeError, TimeoutError, etc.) pass through the requests API "
            "unwrapped. They should be caught in adapters.py and re-raised as the appropriate "
            "requests.exceptions type so callers only need to handle requests exceptions."
        ),
    },
    {
        "id": "psf__requests-3362", "type": "logic_debug",
        "problem": (
            "Response.iter_content(decode_unicode=True) and Response.text use different decoding "
            "logic, producing inconsistent results. iter_content should use the same encoding "
            "detection as Response.text (apparent_encoding fallback)."
        ),
    },
    {
        "id": "mwaskom__seaborn-2848", "type": "logic_debug",
        "problem": (
            "pairplot fails with KeyError when hue_order contains values not present in the data. "
            "In seaborn 0.11+, passing hue_order=['a','b','c'] when data only has ['a','b'] "
            "raises KeyError. Missing hue values should be ignored or handled gracefully."
        ),
    },
    {
        "id": "mwaskom__seaborn-3407", "type": "logic_debug",
        "problem": (
            "pairplot raises KeyError with MultiIndex DataFrame. "
            "When the input DataFrame has a MultiIndex, pairplot fails with a KeyError "
            "because it tries to use MultiIndex tuples as column names. "
            "The DataFrame should be flattened or the index handled before plotting."
        ),
    },
    {
        "id": "pallets__flask-4045", "type": "feature",
        "problem": (
            "Raise an error when a Blueprint name contains a dot. "
            "Dots in blueprint names break url_for() because dots are used as separators. "
            "Blueprint.__init__ should raise ValueError if the name contains a dot."
        ),
    },
    {
        "id": "pallets__flask-5063", "type": "feature",
        "problem": (
            "Flask url_for / routes should expose subdomain and server_name information. "
            "Currently there is no easy way to inspect which subdomain a route belongs to. "
            "Expose subdomain info in the URL map or route listing."
        ),
    },
    {
        "id": "pydata__xarray-3364", "type": "feature",
        "problem": (
            "Add option to ignore missing variables when concatenating datasets. "
            "xr.concat() raises ValueError if datasets have different variables. "
            "Add a data_vars='minimal' or join option to skip variables missing from some datasets."
        ),
    },
    {
        "id": "pydata__xarray-4094", "type": "logic_debug",
        "problem": (
            "to_unstacked_dataset is broken for single-dimension variables. "
            "Dataset.to_stacked_array().to_unstacked_dataset() raises ValueError for variables "
            "that have only one dimension. The unstack logic fails to handle the single-dim case."
        ),
    },
    {
        "id": "pydata__xarray-4248", "type": "feature",
        "problem": (
            "Feature request: show units in Dataset and DataArray overview repr. "
            "If a variable has a 'units' attribute, include it in the repr output "
            "next to the dtype, e.g. float64 [m/s], so units are visible at a glance."
        ),
    },
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
                      f"duration={r['duration_s']:.1f}s  changed={r['code_changed']}")

            measured = [r for r in run_results if r["energy_kwh"] > 0]
            avg = lambda key: sum(r[key] for r in measured) / len(measured) if measured else 0.0
            print(f"  --> avg energy   : {avg('energy_kwh'):.8f} kWh")
            print(f"  --> avg duration : {avg('duration_s'):.1f} s")
            print(f"  --> code_changed : {sum(r['code_changed'] for r in run_results)}/{len(pending)}")
            print(f"  --> (accuracy via evaluate_patches.py + harness)")

            all_results.append({
                "task_id":       task_id,
                "condition":     condition,
                "condition_label": cond_label,
                "avg_energy":    avg("energy_kwh"),
                "avg_emissions": avg("emissions_kg"),
                "avg_duration":  avg("duration_s"),
                "n_valid":       len(measured),
            })

    # ── Summary table ──────────────────────────────────────────────────
    print("\n" + "=" * 70)
    print("BATCH SUMMARY  (avg energy kWh per condition)")
    print("=" * 70)
    print(f"{'Task':<38} {'baseline':>12} {'skill':>12} {'best':>8}")
    print("-" * 70)

    def get_avg(task_id, cond_label):
        for r in all_results:
            if r["task_id"] == task_id and r.get("condition_label", r["condition"]) == cond_label:
                return r["avg_energy"]
        return None

    for task in active_batch:
        tid = task["id"]
        short = tid.split("__")[1][:35]
        b = get_avg(tid, "baseline")
        s = get_avg(tid, "task_specific_skill")
        vals = {k: v for k, v in [("baseline", b), ("skill", s)] if v}
        best = min(vals, key=vals.get) if vals else "?"
        fmt = lambda v: f"{v:.6f}" if v else "     n/a"
        print(f"{short:<38} {fmt(b):>12} {fmt(s):>12} {best:>8}")

    print(f"\nAll results saved to: {experiment.RESULTS_CSV}")
    print("=" * 70)

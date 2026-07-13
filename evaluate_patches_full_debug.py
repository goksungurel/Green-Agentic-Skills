"""
evaluate_patches_full_debug.py
-------------------------------
Same as evaluate_patches.py, but for the separate full-systematic-debug-skill
pilot (results/patches_full_debug/ → results/accuracy_full_debug.csv).

Does not touch results/patches/ or results/accuracy.csv (the main pipeline).

Usage:
    python3 evaluate_patches_full_debug.py
    python3 evaluate_patches_full_debug.py --task astropy__astropy-6938
    python3 evaluate_patches_full_debug.py --patch results/patches_full_debug/...patch
"""

import argparse
import csv
import json
import os
import subprocess
import sys
import tempfile

_HERE        = os.path.dirname(os.path.abspath(__file__))
PATCH_DIR    = os.path.join(_HERE, "results", "patches_full_debug")
ACCURACY_CSV = os.path.join(_HERE, "results", "accuracy_full_debug.csv")
ACCURACY_HEADERS = ["task_id", "condition", "run", "resolved"]

PATCH_TIMEOUT = 1800


def parse_patch_name(fname: str):
    name = fname.replace(".patch", "")
    parts = name.rsplit("__", 2)
    if len(parts) != 3:
        return None
    task_id, condition, run_str = parts
    run = run_str.replace("run", "")
    return task_id, condition, run


def load_valid_syntax(csv_path: str = None) -> dict:
    """(task_id, condition, run) -> True/False/None, sourced from
    results/runs_full_debug.csv's valid_syntax column (py_compile check
    already done in run_full_debug_pilot.py)."""
    path = csv_path or os.path.join(_HERE, "results", "runs_full_debug.csv")
    lookup = {}
    if not os.path.exists(path):
        return lookup
    with open(path, newline="") as f:
        for row in csv.DictReader(f):
            key = (row["task_id"], row["condition"], row["run"])
            vs = row.get("valid_syntax", "n/a")
            lookup[key] = None if vs == "n/a" else (vs == "True")
    return lookup


def build_predictions(patch_files: list, valid_syntax: dict = None) -> list:
    valid_syntax = valid_syntax or {}
    predictions = []
    for fpath in patch_files:
        fname = os.path.basename(fpath)
        parsed = parse_patch_name(fname)
        if not parsed:
            print(f"  [SKIP] Cannot parse filename: {fname}")
            continue
        task_id, condition, run = parsed
        if valid_syntax.get((task_id, condition, run)) is False:
            print(f"  [SKIP] Invalid syntax (py_compile failed), not sent to harness: {fname}")
            continue
        with open(fpath) as f:
            patch_content = f.read()
        if not patch_content.strip():
            print(f"  [SKIP] Empty patch: {fname}")
            continue
        predictions.append({
            "instance_id":        task_id,
            "model_patch":        patch_content,
            # unique per (task_id, condition, run) — avoids run_id collisions
            "model_name_or_path": f"greenskillfd_{task_id}_{condition}_run{run}",
            "_condition": condition,
            "_run":       run,
        })
    return predictions


def _cleanup_reports(run_id: str):
    for fname in os.listdir(_HERE):
        if fname.endswith(f".{run_id}.json"):
            try:
                os.unlink(os.path.join(_HERE, fname))
            except OSError:
                pass


def run_harness_single(prediction: dict) -> bool:
    run_id    = prediction["model_name_or_path"]
    instance  = prediction["instance_id"]
    clean     = {k: v for k, v in prediction.items() if not k.startswith("_")}

    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".json", delete=False, dir=_HERE
    ) as tf:
        json.dump([clean], tf)
        pred_path = tf.name

    cmd = [
        sys.executable, "-m", "swebench.harness.run_evaluation",
        "--max_workers",  "1",
        "--instance_ids", instance,
        "--predictions_path", pred_path,
        "--run_id", run_id,
    ]

    timed_out = False
    try:
        try:
            subprocess.run(cmd, capture_output=False, text=True, timeout=PATCH_TIMEOUT)
        except subprocess.TimeoutExpired:
            timed_out = True
    finally:
        try:
            os.unlink(pred_path)
        except OSError:
            pass

    if timed_out:
        print(f"    [TIMEOUT after {PATCH_TIMEOUT}s]")
        _cleanup_reports(run_id)
        return False

    report_path = os.path.join(_HERE, f"{run_id}.{run_id}.json")
    if not os.path.exists(report_path):
        for fname in os.listdir(_HERE):
            if fname.endswith(f".{run_id}.json"):
                report_path = os.path.join(_HERE, fname)
                break
        else:
            print(f"    [WARN] No report found for run_id={run_id}")
            return False

    try:
        with open(report_path) as f:
            report = json.load(f)
        return instance in set(report.get("resolved_ids", []))
    finally:
        try:
            os.unlink(report_path)
        except OSError:
            pass


def load_existing_accuracy() -> set:
    done = set()
    if not os.path.exists(ACCURACY_CSV):
        return done
    with open(ACCURACY_CSV, newline="") as f:
        for row in csv.DictReader(f):
            done.add((row["task_id"], row["condition"], row["run"]))
    return done


def append_accuracy(rows: list):
    write_header = not os.path.exists(ACCURACY_CSV)
    with open(ACCURACY_CSV, "a", newline="") as f:
        w = csv.DictWriter(f, fieldnames=ACCURACY_HEADERS)
        if write_header:
            w.writeheader()
        w.writerows(rows)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--task",  help="Only evaluate patches for this task_id")
    parser.add_argument("--patch", help="Evaluate a single patch file")
    args = parser.parse_args()

    os.makedirs(os.path.join(_HERE, "results"), exist_ok=True)

    if args.patch:
        patch_files = [args.patch]
    else:
        if not os.path.isdir(PATCH_DIR):
            print(f"No patch dir found at {PATCH_DIR}. Run run_full_debug_pilot.py first.")
            return
        all_patches = sorted(
            os.path.join(PATCH_DIR, f)
            for f in os.listdir(PATCH_DIR)
            if f.endswith(".patch")
        )
        if args.task:
            patch_files = [p for p in all_patches if os.path.basename(p).startswith(args.task)]
        else:
            patch_files = all_patches

    if not patch_files:
        print("No patch files found.")
        return

    print(f"Found {len(patch_files)} patch file(s).")

    done = load_existing_accuracy()
    pending = []
    for fpath in patch_files:
        parsed = parse_patch_name(os.path.basename(fpath))
        if parsed and parsed not in done:
            pending.append(fpath)
        elif parsed:
            print(f"  [SKIP] Already evaluated: {os.path.basename(fpath)}")

    if not pending:
        print("All patches already evaluated.")
        return

    valid_syntax = load_valid_syntax()
    predictions = build_predictions(pending, valid_syntax)
    if not predictions:
        print("No valid predictions to evaluate.")
        return

    print(f"\nEvaluating {len(predictions)} patch(es) — one at a time (timeout {PATCH_TIMEOUT}s each)...\n")

    resolved_count = 0
    for i, pred in enumerate(predictions, 1):
        label = f"{pred['instance_id']} [{pred['_condition']}] run{pred['_run']}"
        print(f"  [{i:3d}/{len(predictions)}] {label} ...", end=" ", flush=True)

        resolved = run_harness_single(pred)
        resolved_count += resolved
        print("RESOLVED" if resolved else "unresolved")

        append_accuracy([{
            "task_id":   pred["instance_id"],
            "condition": pred["_condition"],
            "run":       pred["_run"],
            "resolved":  resolved,
        }])

    print(f"\n{'='*60}")
    print(f"Done. {resolved_count}/{len(predictions)} patches resolved.")
    print(f"Accuracy results saved to: {ACCURACY_CSV}")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()

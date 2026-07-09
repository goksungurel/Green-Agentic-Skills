"""
evaluate_patches.py
-------------------
Evaluates agent patches using the SWE-bench harness.

For each .patch file in results/patches/, applies it to the task repo and
runs the official FAIL_TO_PASS / PASS_TO_PASS tests via Docker.

Writes results to results/accuracy.csv with columns:
    task_id, condition, run, resolved

Usage:
    python3 evaluate_patches.py              # evaluate all patches
    python3 evaluate_patches.py --task astropy__astropy-6938
    python3 evaluate_patches.py --patch results/patches/...patch
"""

import argparse
import csv
import json
import os
import subprocess
import sys
import tempfile

_HERE        = os.path.dirname(os.path.abspath(__file__))
PATCH_DIR    = os.path.join(_HERE, "results", "patches")
ACCURACY_CSV = os.path.join(_HERE, "results", "accuracy.csv")
ACCURACY_HEADERS = ["task_id", "condition", "run", "resolved"]

# Per-patch timeout: 30 min is generous for any single Docker run
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
    """Returns dict keyed by (task_id, condition, run) -> valid_syntax.

    Value is True/False, or None if not applicable (runs.csv has "n/a",
    meaning no code was changed at all — not the same as a broken change).
    Used to skip patches that experiment.py's py_compile check already
    proved are syntactically broken, so we don't burn Docker time on a
    guaranteed-negative harness run.
    """
    path = csv_path or os.path.join(_HERE, "results", "runs.csv")
    lookup = {}
    if not os.path.exists(path):
        return lookup
    with open(path, newline="") as f:
        for row in csv.DictReader(f):
            key = (row["task_id"], row["condition"], row["run"])
            vs = row.get("valid_syntax", "n/a")
            lookup[key] = None if vs == "n/a" else (vs == "True")
    return lookup


def build_predictions(patch_files: list[str], valid_syntax: dict = None) -> list[dict]:
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
            print(f"  [SKIP] Invalid syntax (py_compile failed in experiment.py), not sent to harness: {fname}")
            continue
        with open(fpath) as f:
            patch_content = f.read()
        if not patch_content.strip():
            print(f"  [SKIP] Empty patch: {fname}")
            continue
        predictions.append({
            "instance_id":        task_id,
            "model_patch":        patch_content,
            # IMPORTANT: must be unique per (task_id, condition, run), not just
            # (condition, run) — otherwise different tasks sharing the same
            # condition/run number collide on the harness's run_id-keyed
            # report file/cache, and one task's resolved result can leak into
            # another's (this caused stale/wrong rows in accuracy.csv).
            "model_name_or_path": f"greenskill_{task_id}_{condition}_run{run}",
            "_condition": condition,
            "_run":       run,
        })
    return predictions


def _cleanup_reports(run_id: str):
    """Remove leftover harness report JSON files."""
    for fname in os.listdir(_HERE):
        if fname.endswith(f".{run_id}.json"):
            try:
                os.unlink(os.path.join(_HERE, fname))
            except OSError:
                pass


def run_harness_single(prediction: dict) -> bool:
    """
    Run the harness for exactly ONE prediction.
    Returns True if resolved, False otherwise (including timeout).
    Uses model_name_or_path as run_id so the report file is predictable.
    """
    run_id    = prediction["model_name_or_path"]  # unique per patch
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
        # Crash-safe: pred_path must never be left behind, regardless of
        # whether subprocess.run times out, raises something else, or
        # succeeds. Previously this unlink sat unconditionally *after* the
        # try/except, so any exception other than TimeoutExpired (e.g. the
        # harness module not being importable) would skip cleanup and leak
        # a tmp*.json file into the project root.
        try:
            os.unlink(pred_path)
        except OSError:
            pass

    if timed_out:
        print(f"    [TIMEOUT after {PATCH_TIMEOUT}s]")
        _cleanup_reports(run_id)
        return False

    # Report file: <model_name_or_path>.<run_id>.json
    # Since run_id == model_name_or_path, the file is <run_id>.<run_id>.json
    # Fall back to globbing in case harness naming differs.
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
        # Crash-safe: report file must be removed even if json.load() fails
        # on a corrupted/partial report.
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


def append_accuracy(rows: list[dict]):
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

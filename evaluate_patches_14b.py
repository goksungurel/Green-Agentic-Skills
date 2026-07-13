"""
evaluate_patches_14b.py
-----------------------
Evaluates 14B pilot patches using the SWE-bench Docker harness.
Reads from  : results/patches_14b/
Writes to   : results/accuracy_14b.csv

Usage:
    python3 evaluate_patches_14b.py
    python3 evaluate_patches_14b.py --task psf__requests-2317
    python3 evaluate_patches_14b.py --patch results/patches_14b/...patch

Identical logic to evaluate_patches.py — only PATCH_DIR and
ACCURACY_CSV paths differ, so the 7B results are never touched.
"""

import argparse
import csv
import json
import os
import subprocess
import tempfile

_HERE            = os.path.dirname(os.path.abspath(__file__))
PATCH_DIR        = os.path.join(_HERE, "results", "patches_14b")
ACCURACY_CSV     = os.path.join(_HERE, "results", "accuracy_14b.csv")
ACCURACY_HEADERS = ["task_id", "condition", "run", "resolved"]

PATCH_TIMEOUT = 1800   # 30 min per patch


def parse_patch_name(fname):
    name  = fname.replace(".patch", "")
    parts = name.rsplit("__", 2)
    if len(parts) != 3:
        return None
    task_id, condition, run_str = parts
    run = run_str.replace("run", "")
    return task_id, condition, run


def build_predictions(patch_files):
    predictions = []
    for fpath in patch_files:
        fname  = os.path.basename(fpath)
        parsed = parse_patch_name(fname)
        if not parsed:
            print(f"  [SKIP] Cannot parse filename: {fname}")
            continue
        task_id, condition, run = parsed
        with open(fpath) as f:
            patch_content = f.read()
        if not patch_content.strip():
            print(f"  [SKIP] Empty patch: {fname}")
            continue
        predictions.append({
            "instance_id":        task_id,
            "model_patch":        patch_content,
            # Unique run_id per (task_id, condition, run) — avoids harness cache collisions
            "model_name_or_path": f"greenskill14b_{task_id}_{condition}_run{run}",
            "_condition": condition,
            "_run":       run,
        })
    return predictions


def _cleanup_reports(run_id):
    for fname in os.listdir(_HERE):
        if fname.endswith(f".{run_id}.json"):
            try:
                os.unlink(os.path.join(_HERE, fname))
            except OSError:
                pass


def run_harness_single(prediction):
    run_id   = prediction["model_name_or_path"]
    instance = prediction["instance_id"]
    clean    = {k: v for k, v in prediction.items() if not k.startswith("_")}

    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".json", delete=False, dir=_HERE
    ) as tf:
        json.dump([clean], tf)
        pred_path = tf.name

    cmd = [
        "python", "-m", "swebench.harness.run_evaluation",
        "--max_workers",  "1",
        "--instance_ids", instance,
        "--predictions_path", pred_path,
        "--run_id", run_id,
    ]

    timed_out = False
    try:
        subprocess.run(cmd, capture_output=False, text=True, timeout=PATCH_TIMEOUT)
    except subprocess.TimeoutExpired:
        timed_out = True

    os.unlink(pred_path)

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

    with open(report_path) as f:
        report = json.load(f)
    os.unlink(report_path)

    return instance in set(report.get("resolved_ids", []))


def load_existing_accuracy():
    done = set()
    if not os.path.exists(ACCURACY_CSV):
        return done
    with open(ACCURACY_CSV, newline="") as f:
        for row in csv.DictReader(f):
            done.add((row["task_id"], row["condition"], row["run"]))
    return done


def append_accuracy(rows):
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

    os.makedirs(PATCH_DIR, exist_ok=True)

    if args.patch:
        patch_files = [args.patch]
    else:
        if not os.path.isdir(PATCH_DIR):
            print(f"Patch directory not found: {PATCH_DIR}")
            print("Run run_qwen14b_pilot.py first.")
            return
        all_patches = sorted(
            os.path.join(PATCH_DIR, f)
            for f in os.listdir(PATCH_DIR)
            if f.endswith(".patch")
        )
        if args.task:
            patch_files = [p for p in all_patches
                           if os.path.basename(p).startswith(args.task)]
        else:
            patch_files = all_patches

    if not patch_files:
        print("No patch files found in", PATCH_DIR)
        return

    print(f"Found {len(patch_files)} patch file(s) in {PATCH_DIR}")

    done    = load_existing_accuracy()
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

    predictions = build_predictions(pending)
    if not predictions:
        print("No valid predictions to evaluate.")
        return

    print(f"\nEvaluating {len(predictions)} patch(es) (timeout {PATCH_TIMEOUT}s each)...\n")

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
    print(f"Results saved to: {ACCURACY_CSV}")
    print(f"Run `python3 analyze_14b.py` for the 7B vs 14B comparison.")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()

"""
evaluate_patches.py
-------------------
Evaluates agent patches using the SWE-bench harness.

For each .patch file in results/patches/, applies it to the task repo and
runs the official FAIL_TO_PASS / PASS_TO_PASS tests via Docker.

Writes results to results/accuracy.csv with columns:
    task_id, condition, run, resolved

Usage:
    # Evaluate all patches
    python3 evaluate_patches.py

    # Evaluate one specific task only
    python3 evaluate_patches.py --task astropy__astropy-6938

    # Evaluate one specific patch file
    python3 evaluate_patches.py --patch results/patches/astropy__astropy-6938__logic_debug_skill__run1.patch
"""

import argparse
import csv
import json
import os
import subprocess
import tempfile

_HERE       = os.path.dirname(os.path.abspath(__file__))
PATCH_DIR   = os.path.join(_HERE, "results", "patches")
ACCURACY_CSV = os.path.join(_HERE, "results", "accuracy.csv")
ACCURACY_HEADERS = ["task_id", "condition", "run", "resolved"]


# ------------------------------------------------------------------
# Parse patch filename → (task_id, condition, run)
# Format: astropy__astropy-6938__logic_debug_skill__run3.patch
# ------------------------------------------------------------------
def parse_patch_name(fname: str):
    name = fname.replace(".patch", "")
    # split from right: last part is runN, second-to-last is condition
    # task_id can contain __ so we split carefully
    parts = name.rsplit("__", 2)
    if len(parts) != 3:
        return None
    task_id, condition, run_str = parts
    run = run_str.replace("run", "")
    return task_id, condition, run


# ------------------------------------------------------------------
# Build predictions JSON for harness
# Format: [{"instance_id": ..., "model_patch": ..., "model_name_or_path": ...}]
# ------------------------------------------------------------------
def build_predictions(patch_files: list[str]) -> list[dict]:
    predictions = []
    for fpath in patch_files:
        fname = os.path.basename(fpath)
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
            "model_name_or_path": f"greenskill_{condition}_run{run}",
            # store metadata so we can map results back
            "_condition": condition,
            "_run":       run,
        })
    return predictions


# ------------------------------------------------------------------
# Run harness for a list of predictions
# Writes a temp predictions.json, calls swebench harness, reads output
# Returns dict: instance_id → resolved (bool)
# ------------------------------------------------------------------
def run_harness(predictions: list[dict], run_id: str = "greenskill") -> dict:
    # harness doesn't want our private _ fields
    clean = [
        {k: v for k, v in p.items() if not k.startswith("_")}
        for p in predictions
    ]

    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".json", delete=False, dir=_HERE
    ) as tf:
        json.dump(clean, tf)
        pred_path = tf.name

    instance_ids = [p["instance_id"] for p in predictions]

    print(f"\n  Running harness for {len(predictions)} instance(s): {instance_ids}")
    print(f"  predictions → {pred_path}")

    cmd = [
        "python", "-m", "swebench.harness.run_evaluation",
        "--max_workers",  "1",
        "--instance_ids", *instance_ids,
        "--predictions_path", pred_path,
        "--run_id", run_id,
    ]

    result = subprocess.run(cmd, capture_output=False, text=True, timeout=3600)

    # harness writes <model_name_or_path>.<run_id>.json
    # model_name_or_path varies per prediction so glob for *.{run_id}.json
    report_path = None
    for fname in os.listdir(_HERE):
        if fname.endswith(f".{run_id}.json"):
            report_path = os.path.join(_HERE, fname)
            break

    os.unlink(pred_path)

    if not report_path:
        print(f"  [WARN] Could not find harness report JSON in {_HERE}")
        return {}

    with open(report_path) as f:
        report = json.load(f)

    resolved_ids = set(report.get("resolved_ids", []))

    # build resolved map: instance_id → bool
    # Note: same task can appear multiple times (different runs), so we use full pred info
    resolved_map = {}
    for p in predictions:
        iid = p["instance_id"]
        key = (iid, p["_condition"], p["_run"])
        resolved_map[key] = iid in resolved_ids

    print(f"  Resolved: {sum(resolved_map.values())}/{len(resolved_map)}")
    return resolved_map


# ------------------------------------------------------------------
# Load existing accuracy results to skip already-evaluated patches
# ------------------------------------------------------------------
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


# ------------------------------------------------------------------
# Main
# ------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--task",  help="Only evaluate patches for this task_id")
    parser.add_argument("--patch", help="Evaluate a single patch file")
    args = parser.parse_args()

    os.makedirs(os.path.join(_HERE, "results"), exist_ok=True)

    # Collect patch files
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

    # Skip already evaluated
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

    print(f"Evaluating {len(pending)} patch(es)...\n")

    predictions = build_predictions(pending)
    if not predictions:
        print("No valid predictions to evaluate.")
        return

    resolved_map = run_harness(predictions, run_id="greenskill-eval")

    # Write accuracy rows
    accuracy_rows = []
    for p in predictions:
        key = (p["instance_id"], p["_condition"], p["_run"])
        accuracy_rows.append({
            "task_id":   p["instance_id"],
            "condition": p["_condition"],
            "run":       p["_run"],
            "resolved":  resolved_map.get(key, False),
        })

    append_accuracy(accuracy_rows)

    print(f"\nAccuracy results saved to: {ACCURACY_CSV}")
    print("=" * 50)
    for row in accuracy_rows:
        status = "RESOLVED" if row["resolved"] else "unresolved"
        print(f"  {row['task_id']} [{row['condition']}] run{row['run']} → {status}")
    print("=" * 50)


if __name__ == "__main__":
    main()

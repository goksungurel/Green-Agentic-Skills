"""
analyze_14b.py
--------------
Compares 14B pilot results (results/runs_14b.csv + results/accuracy_14b.csv)
against the 7B pilot results (results/runs.csv + results/accuracy.csv)
for the same 3 tasks.

Run after:
  1. python3 run_qwen14b_pilot.py
  2. python3 evaluate_patches_14b.py   (if harness evaluation is done)

If accuracy_14b.csv doesn't exist yet, the script prints energy/step stats
only and skips accuracy rows.
"""

import csv
import os
from collections import defaultdict

_HERE = os.path.dirname(os.path.abspath(__file__))

PILOT_TASKS = [
    "psf__requests-2317",
    "psf__requests-2148",
    "django__django-11039",
]

# ------------------------------------------------------------------
# Load helpers
# ------------------------------------------------------------------

def load_runs(csv_path):
    """Returns list of dicts from a runs CSV. Returns [] if file missing."""
    if not os.path.exists(csv_path):
        return []
    with open(csv_path, newline="") as f:
        return list(csv.DictReader(f))


def load_accuracy(csv_path):
    """Returns {(task_id, condition, run): resolved_bool}. Returns {} if missing."""
    if not os.path.exists(csv_path):
        return {}
    result = {}
    with open(csv_path, newline="") as f:
        for row in csv.DictReader(f):
            key = (row["task_id"], row["condition"], int(row["run"]))
            result[key] = row.get("resolved", "").lower() == "true"
    return result


def stats(rows, accuracy_map):
    """
    Compute per-(task, condition) stats from run rows + accuracy map.
    Returns dict: (task_id, condition) -> stats dict.
    """
    grouped = defaultdict(list)
    for r in rows:
        grouped[(r["task_id"], r["condition"])].append(r)

    out = {}
    for (tid, cond), rlist in grouped.items():
        if tid not in PILOT_TASKS:
            continue
        measured = [r for r in rlist if float(r["energy_kwh"]) > 0]
        n_total  = len(rlist)
        n_meas   = len(measured)
        avg_e    = sum(float(r["energy_kwh"]) for r in measured) / n_meas * 1000 if n_meas else 0
        avg_s    = sum(int(r["steps"]) for r in measured) / n_meas if n_meas else 0
        n_changed = sum(1 for r in rlist if str(r["code_changed"]).lower() == "true"
                                            or r["code_changed"] is True)
        # valid_syntax: count runs where valid_syntax == True (bool or string)
        n_valid  = sum(1 for r in rlist
                       if str(r.get("valid_syntax", "")).lower() == "true"
                       or r.get("valid_syntax") is True)

        # Accuracy
        resolved_keys = [(tid, cond, int(r["run"])) for r in rlist]
        n_evaluated = sum(1 for k in resolved_keys if k in accuracy_map)
        n_resolved  = sum(1 for k in resolved_keys if accuracy_map.get(k, False))

        out[(tid, cond)] = {
            "n_runs":    n_total,
            "avg_mwh":   avg_e,
            "avg_steps": avg_s,
            "n_changed": n_changed,
            "n_valid":   n_valid,
            "n_eval":    n_evaluated,
            "n_res":     n_resolved,
            "res_rate":  f"{n_resolved}/{n_evaluated}" if n_evaluated else "n/a",
        }
    return out


# ------------------------------------------------------------------
# Main
# ------------------------------------------------------------------

def main():
    runs_7b  = load_runs(os.path.join(_HERE, "results", "runs.csv"))
    runs_14b = load_runs(os.path.join(_HERE, "results", "runs_14b.csv"))
    acc_7b   = load_accuracy(os.path.join(_HERE, "results", "accuracy.csv"))
    acc_14b  = load_accuracy(os.path.join(_HERE, "results", "accuracy_14b.csv"))

    stats_7b  = stats(runs_7b,  acc_7b)
    stats_14b = stats(runs_14b, acc_14b)

    if not runs_14b:
        print("No 14B results found. Run run_qwen14b_pilot.py first.")
        return

    print("=" * 78)
    print("GreenSkill — 7B vs 14B Comparison  (pilot tasks only)")
    print("=" * 78)

    for task_id in PILOT_TASKS:
        print(f"\n  Task: {task_id}")
        print(f"  {'Condition':<24} {'Model':<5}  {'mWh':>8}  {'Steps':>6}  {'Changed':>8}  {'Resolved':>10}")
        print("  " + "-" * 68)

        # Find conditions that appear in either model's results for this task
        conds_seen = set()
        for (tid, cond) in list(stats_7b.keys()) + list(stats_14b.keys()):
            if tid == task_id:
                conds_seen.add(cond)

        for cond in sorted(conds_seen):
            for label, s_map in [("7B", stats_7b), ("14B", stats_14b)]:
                s = s_map.get((task_id, cond))
                if s is None:
                    print(f"  {cond:<24} {label:<5}  {'—':>8}  {'—':>6}  {'—':>8}  {'—':>10}")
                else:
                    print(f"  {cond:<24} {label:<5}  {s['avg_mwh']:>8.3f}  "
                          f"{s['avg_steps']:>6.1f}  "
                          f"{s['n_changed']}/{s['n_runs']:>1}  changed  "
                          f"{s['res_rate']:>10}")

    # ------------------------------------------------------------------
    # Cross-task energy summary
    # ------------------------------------------------------------------
    print("\n" + "=" * 78)
    print("ENERGY SUMMARY — baseline vs skill, 7B vs 14B")
    print("=" * 78)
    print(f"  {'Model':<5}  {'Condition':<24}  {'Avg mWh (3 tasks)':>18}  {'Avg Steps':>10}")
    print("  " + "-" * 62)

    for label, s_map in [("7B", stats_7b), ("14B", stats_14b)]:
        for cond in ["baseline", "logic_debug_skill", "exception_debug_skill"]:
            rows_for_cond = [s for (tid, c), s in s_map.items()
                             if c == cond and tid in PILOT_TASKS]
            if not rows_for_cond:
                continue
            avg_e = sum(r["avg_mwh"]   for r in rows_for_cond) / len(rows_for_cond)
            avg_s = sum(r["avg_steps"] for r in rows_for_cond) / len(rows_for_cond)
            print(f"  {label:<5}  {cond:<24}  {avg_e:>18.3f}  {avg_s:>10.1f}")

    print()
    if not acc_14b:
        print("  NOTE: accuracy_14b.csv not found — run evaluate_patches_14b.py")
        print("        for resolve rate numbers.")
    print()


if __name__ == "__main__":
    main()

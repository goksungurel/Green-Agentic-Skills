"""
validate_blueprint_fix.py
--------------------------
Targeted re-validation for the mini.yaml "literal placeholder copy-paste" fix.

Background:
  Before the fix, mini.yaml's Workflow showed two illustrative example
  commands as literal backtick'd shell commands:
      `grep -rn "class Blueprint"`
      `grep -rn "def method_name"`
  Qwen2.5-Coder:7b copy-pasted these verbatim instead of substituting the
  real class/function name from the issue. This wasted 100% of the runs for:
      django__django-11039        (10/10 runs: baseline + logic_debug_skill)
      pydata__xarray-3364          (6/10 runs seen: baseline + feature_skill)
      psf__requests-2317 x logic_debug_skill (5/5 runs)
  all ending in LimitsExceeded with code_changed=False.

This script re-runs ONLY those exact (task, condition) pairs, using run
indices 6 and 7 so they do not overwrite/collide with the existing run1-5
data in results/runs.csv (kept for before/after comparison).

Usage:
    python3 validate_blueprint_fix.py

Run this in a terminal with background tabs/apps closed for clean energy
measurement (per the project's CodeCarbon setup) — this script does not
launch itself; it's meant to be run manually after you're ready.
"""

import json
import os

import experiment

_HERE = os.path.dirname(os.path.abspath(__file__))

TARGETS = [
    ("django__django-11039", "baseline"),
    ("django__django-11039", "logic_debug_skill"),
    ("pydata__xarray-3364", "baseline"),
    ("pydata__xarray-3364", "feature_skill"),
    ("psf__requests-2317", "logic_debug_skill"),
]

# Fresh run indices — won't collide with the existing run1-5 rows/trajectories,
# so old (broken) data stays intact for before/after comparison.
RUN_INDICES = [6, 7]

LITERAL_PLACEHOLDERS = ["class Blueprint", "def method_name"]


def commands_from_trajectory(traj_file: str) -> list[str]:
    try:
        with open(traj_file) as f:
            data = json.load(f)
    except Exception:
        return []
    cmds = []
    for msg in data.get("messages", []):
        for tc in msg.get("tool_calls", []):
            args_str = tc.get("function", {}).get("arguments", "")
            try:
                cmd = json.loads(args_str).get("command", "")
            except Exception:
                cmd = args_str
            cmds.append(cmd)
    return cmds


def main():
    experiment.ensure_results_dir()

    print("=" * 78)
    print("VALIDATING mini.yaml literal-placeholder fix")
    print(f"Targets: {len(TARGETS)} (task, condition) pairs x {len(RUN_INDICES)} runs"
          f" = {len(TARGETS) * len(RUN_INDICES)} total runs")
    print("=" * 78)

    summary = []

    for task_id, condition in TARGETS:
        meta = experiment.get_task_meta(task_id)
        problem = meta.get("problem_statement", "")
        if not problem:
            print(f"[ERROR] No problem_statement found for {task_id} — skipping.")
            continue

        for run_index in RUN_INDICES:
            print(f"\n--- {task_id} [{condition}] run{run_index} ---", flush=True)
            r = experiment.run_once(task_id, problem, condition, run_index=run_index)
            experiment.append_result(r)

            traj_file = os.path.join(
                _HERE, experiment.TRAJ_DIR, f"{task_id}__{condition}__run{run_index}.json"
            )
            cmds = commands_from_trajectory(traj_file)
            literal_hit = any(
                any(p in c for p in LITERAL_PLACEHOLDERS) for c in cmds
            )

            print(f"  exit_status   : {r['exit_status']}")
            print(f"  steps         : {r['steps']}")
            print(f"  code_changed  : {r['code_changed']}")
            print(f"  valid_syntax  : {r['valid_syntax']}")
            print(f"  literal-bug recurred: {literal_hit}")

            summary.append({
                "task_id": task_id, "condition": condition, "run": run_index,
                "exit_status": r["exit_status"], "code_changed": r["code_changed"],
                "valid_syntax": r["valid_syntax"], "literal_hit": literal_hit,
            })

    print("\n" + "=" * 78)
    print("VALIDATION SUMMARY")
    print("=" * 78)
    print(f"{'Task':<26} {'Condition':<20} {'Run':>3} {'Exit':<15} {'Changed':>8} {'Valid':>6} {'BugBack':>8}")
    print("-" * 78)
    for s in summary:
        print(f"{s['task_id']:<26} {s['condition']:<20} {s['run']:>3} "
              f"{s['exit_status']:<15} {str(s['code_changed']):>8} "
              f"{str(s['valid_syntax']):>6} {str(s['literal_hit']):>8}")

    n_changed = sum(1 for s in summary if s["code_changed"])
    n_literal = sum(1 for s in summary if s["literal_hit"])
    print("-" * 78)
    print(f"Real code changes : {n_changed}/{len(summary)}")
    print(f"Literal bug back  : {n_literal}/{len(summary)}  (should be 0 if the fix worked)")
    print("=" * 78)


if __name__ == "__main__":
    main()

"""
validate_fixes_v2.py
---------------------
Re-validation for the THREE mini.yaml fixes applied after the first
validation round (run6/run7, see validate_blueprint_fix.py):

  1. FOUND_FILE_PATH placeholder fix — replaced the literal `/path/to/file.py`
     example path (which the model copy-pasted into a real `git diff --
     /path/to/file.py` command, causing `fatal: Invalid path`) with an
     unambiguous non-path-shaped placeholder + explicit "substitute this"
     warnings at every occurrence.
  2. sed `\n`-in-replacement footgun fix — added an explicit anti-example
     warning that `\n` inside a sed `s/old/new/` replacement is NOT a real
     newline on this system (writes literal backslash+n, breaks Python).
  3. sed -i removed entirely — every edit (one-line or multi-line) must now
     use the python3 `.replace()` pattern; `sed -i` is forbidden, only
     `sed -n` (read-only) remains allowed.

This script re-runs the same 5 (task, condition) pairs used in round 1 —
the ones that were 100% wasted by the original Blueprint/method_name bug —
using FRESH run indices (8, 9) so they don't collide with run1-5 (original
broken baseline) or run6-7 (round 1 validation) data already in
results/runs.csv. All three datasets stay intact for before/after/after-after
comparison.

For each run, scans the new trajectory for:
  - literal_hit_v1   : recurrence of the original "class Blueprint" /
                       "def method_name" bug (should still be 0, sanity check)
  - literal_hit_path : recurrence of literal "FOUND_FILE_PATH" or
                       "/path/to/file.py" typed into a real command
  - sed_i_used       : any `sed -i` command issued (should be 0 now — sed -i
                       is forbidden in the prompt; this checks the model
                       actually complied)
  - newline_footgun  : a literal two-character `\n` sequence inside a sed
                       replacement (should be impossible now since sed -i
                       shouldn't appear at all, but checked directly anyway)

Usage:
    python3 validate_fixes_v2.py

Run this in a terminal with background tabs/apps closed for clean energy
measurement, same as the previous validation run. This script does not
launch itself — run it manually when ready.
"""

import json
import os
import re

import experiment

_HERE = os.path.dirname(os.path.abspath(__file__))

TARGETS = [
    ("django__django-11039", "baseline"),
    ("django__django-11039", "logic_debug_skill"),
    ("pydata__xarray-3364", "baseline"),
    ("pydata__xarray-3364", "feature_skill"),
    ("psf__requests-2317", "logic_debug_skill"),
]

# Fresh run indices — round 1 used 6/7, so use 8/9 here to keep all three
# datasets (run1-5, run6-7, run8-9) intact for comparison.
RUN_INDICES = [8, 9]

LITERAL_PLACEHOLDERS_V1 = ["class Blueprint", "def method_name"]
LITERAL_PLACEHOLDERS_PATH = ["FOUND_FILE_PATH", "/path/to/file.py"]


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

    print("=" * 90)
    print("VALIDATING round-2 mini.yaml fixes (FOUND_FILE_PATH, sed \\n footgun, sed -i removal)")
    print(f"Targets: {len(TARGETS)} (task, condition) pairs x {len(RUN_INDICES)} runs"
          f" = {len(TARGETS) * len(RUN_INDICES)} total runs")
    print("=" * 90)

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

            literal_hit_v1 = any(
                any(p in c for p in LITERAL_PLACEHOLDERS_V1) for c in cmds
            )
            literal_hit_path = any(
                any(p in c for p in LITERAL_PLACEHOLDERS_PATH) for c in cmds
            )
            sed_i_used = any(re.search(r"\bsed\s+-i\b", c) for c in cmds)
            newline_footgun = any(
                re.search(r"\bsed\s+-i\b.*\\n", c) for c in cmds
            )

            print(f"  exit_status        : {r['exit_status']}")
            print(f"  steps              : {r['steps']}")
            print(f"  code_changed       : {r['code_changed']}")
            print(f"  valid_syntax       : {r['valid_syntax']}")
            print(f"  literal bug v1 (Blueprint/method_name) recurred : {literal_hit_v1}")
            print(f"  literal path bug (FOUND_FILE_PATH/path/to) recurred : {literal_hit_path}")
            print(f"  sed -i used (should be False now) : {sed_i_used}")
            print(f"  sed \\n footgun pattern seen        : {newline_footgun}")

            summary.append({
                "task_id": task_id, "condition": condition, "run": run_index,
                "exit_status": r["exit_status"], "code_changed": r["code_changed"],
                "valid_syntax": r["valid_syntax"],
                "literal_hit_v1": literal_hit_v1,
                "literal_hit_path": literal_hit_path,
                "sed_i_used": sed_i_used,
                "newline_footgun": newline_footgun,
            })

    print("\n" + "=" * 90)
    print("VALIDATION SUMMARY")
    print("=" * 90)
    footgun_hdr = "nFoot"
    print(f"{'Task':<24} {'Condition':<18} {'Run':>3} {'Exit':<13} {'Chg':>4} {'Valid':>6} "
          f"{'V1Bug':>6} {'PathBug':>8} {'sedI':>5} {footgun_hdr:>7}")
    print("-" * 90)
    for s in summary:
        print(f"{s['task_id']:<24} {s['condition']:<18} {s['run']:>3} "
              f"{s['exit_status']:<13} {str(s['code_changed']):>4} "
              f"{str(s['valid_syntax']):>6} {str(s['literal_hit_v1']):>6} "
              f"{str(s['literal_hit_path']):>8} {str(s['sed_i_used']):>5} "
              f"{str(s['newline_footgun']):>7}")

    n = len(summary)
    n_changed       = sum(1 for s in summary if s["code_changed"])
    n_valid_changed = sum(1 for s in summary if s["code_changed"] and s["valid_syntax"] is True)
    n_v1            = sum(1 for s in summary if s["literal_hit_v1"])
    n_path          = sum(1 for s in summary if s["literal_hit_path"])
    n_sedi          = sum(1 for s in summary if s["sed_i_used"])
    n_footgun       = sum(1 for s in summary if s["newline_footgun"])

    print("-" * 90)
    print(f"Real code changes (changed)       : {n_changed}/{n}")
    print(f"Real code changes (changed+valid) : {n_valid_changed}/{n}  <- the number that actually matters")
    print(f"Blueprint/method_name bug back    : {n_v1}/{n}  (should be 0)")
    print(f"FOUND_FILE_PATH/path bug back     : {n_path}/{n}  (should be 0 if today's fix worked)")
    print(f"sed -i used despite being banned  : {n_sedi}/{n}  (should be 0 if today's fix worked)")
    print(f"sed \\n footgun pattern seen        : {n_footgun}/{n}  (should be 0 — sed -i shouldn't even appear)")
    print("=" * 90)


if __name__ == "__main__":
    main()

"""
validate_dedup_fix.py
----------------------
Re-validates dedup_agent.py + the skill-file placeholder fix together on the
same 3 (task, condition) pairs as the first dedup validation round (run10/11):

  - django__django-11039      / logic_debug_skill   (repeated "def sqlmigrate" grep)
  - pydata__xarray-3364        / feature_skill        (repeated "xray.concat" grep)
  - psf__requests-2317         / logic_debug_skill   (repeated "def builtin_str" / "def method" grep)

Round 1 (run10/11) confirmed the dedup-guard itself works (nudge fired 6/6,
django-11039 fully recovered, xarray-3364 partially recovered) but also
surfaced a NEW root cause for the psf__requests-2317 holdout: the model was
searching `grep -rn "def method"` / `"class method"` -- neither word comes
from the real issue text (which is about `builtin_str`). Traced to
skills/logic_debug_skill.md's own example commands using literal-looking
placeholders ("function_name", "ClassName") with no "this is not literal
text" warning -- same bug class as the already-fixed mini.yaml
Blueprint/method_name issue, just in a file that was never audited for it.
skills/feature_skill.md had the identical pattern ("def method(self, ...,
new_param=None)"). Both were rewritten to ALL_CAPS placeholders
(REAL_FUNCTION_NAME, REAL_CLASS_NAME, REAL_METHOD_NAME, REAL_PARAM_NAME)
with explicit substitution warnings.

Round 2 (run12/13) confirmed the skill-file placeholder fix fully resolved
psf__requests-2317 (2/2 Submitted, changed+valid, nudge never even fired --
the model found "builtin_str" directly). django-11039 stayed stable (2/2
changed+valid). xarray-3364 still failed (run12 Submitted/no code change,
run13 LimitsExceeded) -- but trajectory inspection showed these are NOT
genuine task difficulty: run13 repeated a byte-identical broken
`python3 -c "..."` one-liner ~17x in a row, each time hitting the same bash
quoting syntax error (returncode 2) -- the dedup-guard didn't catch it
because its original trigger only fired on a previous EMPTY output, not a
previous ERROR output. run12 hit the separate, already-known "submits
despite an empty git diff" bug.

Round 3 (run14/15) confirmed the generalized trigger (empty OR returncode!=0)
is wired correctly (StuckRepetition fires at step 3 for new repeats), but
all 4 stuck cases were the old "repeated empty grep" pattern again (not the
quoting-error case we targeted) -- pure run-to-run model variance. The
specific quoting-error repeat from run13 did not recur in this 6-run sample.

This round (run16/17) adds the submit guard: DedupAgent now blocks
COMPLETE_TASK_AND_SUBMIT_FINAL_OUTPUT when `git diff HEAD` is empty,
returning a corrective message instead of letting the empty patch through.
Target: xarray-3364/feature_skill run12 exhibited the exact failure mode
(replace ran silently, diff empty, model submitted anyway). Check whether
the guard now forces a retry in that scenario.

Fresh run indices (16, 17) are used so they don't collide with run1-15
already in results/runs.csv.

For each run, scans the new trajectory for:
  - nudge_triggered     : did the dedup-guard's corrective message
                           ("[dedup-guard] ...") appear at all? If yes, the
                           model repeated an empty-output command at least
                           once -- expected given history, the question is
                           what happens next.
  - stuck_repetition     : exit_status == "StuckRepetition" -- the model
                           ignored the nudge too and the run was aborted
                           early rather than burning the full step budget.
  - adapted_after_nudge  : nudge_triggered AND NOT stuck_repetition AND the
                           run did not end in LimitsExceeded either -- i.e.
                           the model saw the nudge and actually changed
                           its command. This is the best-case outcome.
  - code_changed / valid_syntax : same as previous validation scripts.

Usage:
    python3 validate_dedup_fix.py

Run this in a terminal with background tabs/apps closed for clean energy
measurement, same as previous validation runs. This script does not launch
itself -- run it manually when ready.
"""

import json
import os

import experiment

_HERE = os.path.dirname(os.path.abspath(__file__))

TARGETS = [
    ("django__django-11039", "logic_debug_skill"),
    ("pydata__xarray-3364", "feature_skill"),
    ("psf__requests-2317", "logic_debug_skill"),
]

RUN_INDICES = [16, 17]


def trajectory_text(traj_file: str) -> tuple[str, dict]:
    try:
        with open(traj_file) as f:
            data = json.load(f)
    except Exception:
        return "", {}
    chunks = []
    for msg in data.get("messages", []):
        content = msg.get("content")
        if isinstance(content, str):
            chunks.append(content)
        for tc in msg.get("tool_calls", []):
            chunks.append(tc.get("function", {}).get("arguments", ""))
    return "\n".join(chunks), data.get("info", {})


def main():
    experiment.ensure_results_dir()

    print("=" * 90)
    print("VALIDATING dedup_agent.py guard against confirmed stuck-repetition trajectories")
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
            text, info = trajectory_text(traj_file)
            exit_status = info.get("exit_status", r["exit_status"])

            nudge_triggered = "[dedup-guard]" in text
            stuck_repetition = exit_status == "StuckRepetition"
            adapted_after_nudge = (
                nudge_triggered and not stuck_repetition and exit_status != "LimitsExceeded"
            )

            print(f"  exit_status         : {exit_status}")
            print(f"  steps               : {r['steps']}")
            print(f"  code_changed        : {r['code_changed']}")
            print(f"  valid_syntax        : {r['valid_syntax']}")
            print(f"  nudge_triggered     : {nudge_triggered}")
            print(f"  stuck_repetition    : {stuck_repetition}  (aborted early instead of burning full budget)")
            print(f"  adapted_after_nudge : {adapted_after_nudge}  (best case: saw nudge, changed approach)")

            summary.append({
                "task_id": task_id, "condition": condition, "run": run_index,
                "exit_status": exit_status, "code_changed": r["code_changed"],
                "valid_syntax": r["valid_syntax"],
                "nudge_triggered": nudge_triggered,
                "stuck_repetition": stuck_repetition,
                "adapted_after_nudge": adapted_after_nudge,
            })

    print("\n" + "=" * 90)
    print("VALIDATION SUMMARY")
    print("=" * 90)
    print(f"{'Task':<24} {'Condition':<18} {'Run':>3} {'Exit':<17} {'Chg':>4} {'Valid':>6} "
          f"{'Nudge':>6} {'Stuck':>6} {'Adapted':>8}")
    print("-" * 90)
    for s in summary:
        print(f"{s['task_id']:<24} {s['condition']:<18} {s['run']:>3} "
              f"{s['exit_status']:<17} {str(s['code_changed']):>4} "
              f"{str(s['valid_syntax']):>6} {str(s['nudge_triggered']):>6} "
              f"{str(s['stuck_repetition']):>6} {str(s['adapted_after_nudge']):>8}")

    n = len(summary)
    n_changed       = sum(1 for s in summary if s["code_changed"])
    n_valid_changed = sum(1 for s in summary if s["code_changed"] and s["valid_syntax"] is True)
    n_nudge         = sum(1 for s in summary if s["nudge_triggered"])
    n_stuck         = sum(1 for s in summary if s["stuck_repetition"])
    n_adapted       = sum(1 for s in summary if s["adapted_after_nudge"])

    print("-" * 90)
    print(f"Real code changes (changed)       : {n_changed}/{n}")
    print(f"Real code changes (changed+valid) : {n_valid_changed}/{n}")
    print(f"Nudge triggered at least once      : {n_nudge}/{n}")
    print(f"Aborted early as StuckRepetition    : {n_stuck}/{n}  (was: silently burned full 25-step budget every time)")
    print(f"Adapted after nudge (best case)     : {n_adapted}/{n}")
    print("=" * 90)


if __name__ == "__main__":
    main()

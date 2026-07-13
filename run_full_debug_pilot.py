"""
run_full_debug_pilot.py
------------------------
Separate, additive experiment: tests the FULL systematic-debugging skill
(skills/full_systematic_debug_skill.md, ~250 lines, 4-phase methodology,
adapted from github.com/obra/superpowers) as ONE unified skill file across
ALL 30 tasks — not split into exception/logic/feature categories like the
main experiment.

  baseline                 — no skill (same condition name/semantics as
                              the main experiment.py, but stored separately)
  full_systematic_debug    — full_systematic_debug_skill.md prepended

30 tasks x 2 conditions x 5 runs = 300 total runs.

This script is fully self-contained (does not import experiment.py or
run_batch.py) and writes to its own files only:
  results/runs_full_debug.csv
  results/trajectories_full_debug/
  results/patches_full_debug/

The main pipeline (experiment.py, run_batch.py, results/runs.csv) is
NOT imported, NOT touched, and NOT at risk of being modified by this file.

Resumable: re-running skips any (task_id, condition, run) already present
in results/runs_full_debug.csv, same pattern as run_batch.py.

Usage:
    python3 run_full_debug_pilot.py              # full 300-run batch
    python3 run_full_debug_pilot.py --only django__django-11039 psf__requests-2317
    python3 run_full_debug_pilot.py --runs 1      # quick smoke test, 1 run/condition
"""

import argparse
import csv
import os
import shutil
import signal
import subprocess
import tempfile
from datetime import datetime

from codecarbon import EmissionsTracker

# ------------------------------------------------------------------
# Configuration
# ------------------------------------------------------------------
MODEL_NAME = "ollama/qwen2.5-coder:7b-32k"   # same model as the main experiment
N_RUNS     = 5
MAX_STEPS  = 25
# 1800s (vs. the main experiment's 1200s): full_systematic_debug_skill.md is
# ~296 lines (~10x the other skill files), which measurably slows down
# per-step processing (smoke test: same task, same 7 steps, 137s baseline vs
# 182.7s full_systematic_debug — 33% slower for identical step count). A
# 1200s wall-clock ceiling would risk cutting off the long-skill condition
# on hard/multi-step tasks purely due to prompt length, not because the
# methodology failed — confounding the thing this pilot exists to measure.
# Isolated to this file only; experiment.py's TIMEOUT stays 1200.
TIMEOUT    = 1800

RESULTS_CSV = "results/runs_full_debug.csv"
TRAJ_DIR    = "results/trajectories_full_debug"
PATCH_DIR   = "results/patches_full_debug"
TASKS_CSV   = "selected_tasks.csv"

_HERE       = os.path.dirname(os.path.abspath(__file__))
MINI_YAML   = os.path.join(_HERE, "mini.yaml")
LOCAL_REPOS = os.path.join(_HERE, "repos")

SKILL_FILES = {
    "baseline":              None,
    "full_systematic_debug": os.path.join(_HERE, "skills", "full_systematic_debug_skill.md"),
}
CONDITIONS = ["baseline", "full_systematic_debug"]

CSV_HEADERS = [
    "timestamp", "task_id", "condition", "run",
    "emissions_kg", "energy_kwh", "duration_s",
    "returncode", "exit_status", "steps", "code_changed", "valid_syntax",
    "model",
]


# ------------------------------------------------------------------
# Helpers (self-contained copies of experiment.py's logic — not
# imported, so this script cannot affect the main pipeline)
# ------------------------------------------------------------------

def build_prompt(skill_file, problem_statement):
    if skill_file and os.path.isfile(skill_file):
        with open(skill_file) as f:
            return f.read() + "\n\n---\n\n" + problem_statement
    return problem_statement


_TASK_META = None
_TASK_ORDER = None

def _load_tasks():
    global _TASK_META, _TASK_ORDER
    meta, order = {}, []
    with open(os.path.join(_HERE, TASKS_CSV), newline="") as f:
        for row in csv.DictReader(f):
            meta[row["instance_id"]] = {
                "repo":              row["repo"],
                "commit":            row["base_commit"],
                "problem_statement": row["problem_statement"],
            }
            order.append(row["instance_id"])
    _TASK_META, _TASK_ORDER = meta, order

def get_task_meta(task_id):
    if _TASK_META is None:
        _load_tasks()
    return _TASK_META.get(task_id, {})

def all_task_ids():
    if _TASK_ORDER is None:
        _load_tasks()
    return list(_TASK_ORDER)


def clone_repo(repo, commit):
    tmpdir = tempfile.mkdtemp(prefix="greenskill_fulldebug_")
    local_mirror = os.path.join(LOCAL_REPOS, repo.replace("/", "__"))
    if os.path.isdir(local_mirror):
        print(f"      local clone {repo} @ {commit[:8]}...", end=" ", flush=True)
        subprocess.run(
            ["git", "clone", "--local", "--quiet", local_mirror, tmpdir],
            check=True, capture_output=True, timeout=60,
        )
    else:
        print(f"      clone github.com/{repo} @ {commit[:8]}...", end=" ", flush=True)
        subprocess.run(
            ["git", "clone", "--filter=blob:none", "--quiet",
             f"https://github.com/{repo}", tmpdir],
            check=True, capture_output=True, timeout=300,
        )
    subprocess.run(
        ["git", "-C", tmpdir, "checkout", "--quiet", commit],
        check=True, capture_output=True, timeout=60,
    )
    print("ok")
    return tmpdir


def parse_trajectory(traj_file):
    try:
        import json
        with open(traj_file) as f:
            d = json.load(f)
        return {
            "exit_status": d["info"].get("exit_status", "unknown"),
            "steps":       d["info"]["model_stats"].get("api_calls", 0),
        }
    except Exception:
        return {"exit_status": "unknown", "steps": 0}


def ensure_results_dirs():
    os.makedirs(os.path.join(_HERE, TRAJ_DIR),  exist_ok=True)
    os.makedirs(os.path.join(_HERE, PATCH_DIR), exist_ok=True)
    csv_path = os.path.join(_HERE, RESULTS_CSV)
    if not os.path.exists(csv_path):
        with open(csv_path, "w", newline="") as f:
            csv.DictWriter(f, fieldnames=CSV_HEADERS).writeheader()


def load_existing_runs():
    done = set()
    csv_path = os.path.join(_HERE, RESULTS_CSV)
    if not os.path.exists(csv_path):
        return done
    with open(csv_path, newline="") as f:
        for row in csv.DictReader(f):
            done.add((row["task_id"], row["condition"], row["run"]))
    return done


def append_result(row):
    csv_path = os.path.join(_HERE, RESULTS_CSV)
    with open(csv_path, "a", newline="") as f:
        csv.DictWriter(f, fieldnames=CSV_HEADERS).writerow(row)


# ------------------------------------------------------------------
# Process-group cleanup.
#
# mini-swe-agent is launched as `bash -c "mini-swe-agent ..."`. If we only
# kill the bash process (what subprocess.run(timeout=...) does by default,
# and what a plain `kill`/`kill -9` on this script's own PID does too),
# the mini-swe-agent grandchild can survive as an orphan and keep burning
# CPU/RAM/Ollama capacity in the background — which was the root cause of
# the multi-hour contamination incident on 2026-07-09/10 (every TIMEOUT,
# not just an external kill, was leaking an orphan). Launching with
# start_new_session=True puts bash + everything it spawns in one new
# process group, so os.killpg can take the whole group down together.
# ------------------------------------------------------------------

_CURRENT_PROC = None  # the Popen currently in flight, for the signal handler below


def _kill_process_group(proc):
    if proc is None or proc.poll() is not None:
        return  # already exited
    try:
        pgid = os.getpgid(proc.pid)
        os.killpg(pgid, signal.SIGKILL)
    except ProcessLookupError:
        pass
    except Exception:
        try:
            proc.kill()
        except Exception:
            pass


def _handle_termination_signal(signum, frame):
    print(f"\n  [SIGNAL {signum}] Stopping — cleaning up current run's process group first...")
    _kill_process_group(_CURRENT_PROC)
    raise SystemExit(1)


# Covers a plain `kill $(cat results/full_debug.pid)` (SIGTERM) and Ctrl+C
# (SIGINT). Cannot cover `kill -9` on this script's own PID — SIGKILL is
# never catchable in Unix, no code can run in response to it. If you ever
# need an immediate/forced stop, follow it with:
#   pkill -9 -f mini-swe-agent
signal.signal(signal.SIGTERM, _handle_termination_signal)
signal.signal(signal.SIGINT, _handle_termination_signal)


# ------------------------------------------------------------------
# Core run (mirrors experiment.py's run_once — separate copy so the
# main pipeline stays untouched)
# ------------------------------------------------------------------

def run_once(task_id, problem_statement, condition, run_index):
    skill_file = SKILL_FILES.get(condition)
    prompt     = build_prompt(skill_file, problem_statement)

    prompt_file = f"/tmp/greenskill_fulldebug_{task_id}_{condition}_run{run_index}.txt"
    with open(prompt_file, "w") as f:
        f.write(prompt)

    traj_file = os.path.join(
        _HERE, TRAJ_DIR,
        f"{task_id}__{condition}__run{run_index}.json"
    )

    meta   = get_task_meta(task_id)
    repo   = meta.get("repo")
    commit = meta.get("commit")

    tracker = EmissionsTracker(
        project_name=f"fulldebug_{task_id}_{condition}_run{run_index}",
        output_dir=os.path.join(_HERE, "results"),
        log_level="error",
        save_to_file=False,
    )
    tracker.start()
    start_time = datetime.now()

    env = os.environ.copy()
    env["MSWEA_COST_TRACKING"] = "ignore_errors"
    env["PYTHONPATH"] = _HERE + (os.pathsep + env["PYTHONPATH"] if env.get("PYTHONPATH") else "")

    timed_out  = False
    returncode = -1
    repo_dir   = None

    global _CURRENT_PROC
    proc = None
    try:
        if repo and commit:
            repo_dir = clone_repo(repo, commit)

        proc = subprocess.Popen(
            [
                "bash", "-c",
                f"mini-swe-agent "
                f"--model {MODEL_NAME} "
                f'--task "$(cat {prompt_file})" '
                f"--yolo "
                f"--exit-immediately "
                f"--agent-class dedup_agent.DedupAgent "
                f"-c {MINI_YAML} "
                f"-c agent.step_limit={MAX_STEPS} "
                f"-o {traj_file}"
            ],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
            env=env, cwd=repo_dir,
            start_new_session=True,  # own process group -> group-killable
        )
        _CURRENT_PROC = proc
        try:
            _out, _err = proc.communicate(timeout=TIMEOUT)
            returncode = proc.returncode
        except subprocess.TimeoutExpired:
            timed_out = True
            print(f"    [TIMEOUT] run {run_index} exceeded {TIMEOUT}s — killing process group")
            _kill_process_group(proc)
            try:
                proc.communicate(timeout=10)
            except Exception:
                pass

    finally:
        _CURRENT_PROC = None
        # Belt-and-suspenders: if we got here via an exception other than
        # TimeoutExpired (e.g. clone_repo failed) and proc was started,
        # make sure its process group isn't left running.
        if proc is not None:
            _kill_process_group(proc)
        actually_changed = False
        valid_syntax     = "n/a"
        if repo_dir and os.path.isdir(repo_dir):
            diff = subprocess.run(
                ["git", "-C", repo_dir, "diff", "HEAD"],
                capture_output=True, text=True,
            )
            if diff.stdout.strip():
                actually_changed = True
                patch_path = os.path.join(
                    _HERE, PATCH_DIR,
                    f"{task_id}__{condition}__run{run_index}.patch"
                )
                with open(patch_path, "w") as pf:
                    pf.write(diff.stdout)

                changed_files = subprocess.run(
                    ["git", "-C", repo_dir, "diff", "--name-only", "HEAD"],
                    capture_output=True, text=True,
                ).stdout.split()
                py_files  = [f for f in changed_files if f.endswith(".py")]
                syntax_ok = True
                for rel_path in py_files:
                    abs_path = os.path.join(repo_dir, rel_path)
                    if not os.path.isfile(abs_path):
                        continue
                    check = subprocess.run(
                        ["python3", "-m", "py_compile", abs_path],
                        capture_output=True, text=True,
                    )
                    if check.returncode != 0:
                        syntax_ok = False
                        break
                valid_syntax = syntax_ok

        if repo_dir:
            shutil.rmtree(repo_dir, ignore_errors=True)
        if os.path.exists(prompt_file):
            os.unlink(prompt_file)

    emissions_kg = tracker.stop() or 0.0
    duration_s   = (datetime.now() - start_time).total_seconds()

    try:
        energy_kwh = tracker._total_energy.kWh
    except Exception:
        energy_kwh = 0.0

    if timed_out:
        emissions_kg = 0.0
        energy_kwh   = 0.0

    traj = parse_trajectory(traj_file)

    return {
        "timestamp":    datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "task_id":      task_id,
        "condition":    condition,
        "run":          run_index,
        "emissions_kg": round(emissions_kg, 10),
        "energy_kwh":   round(energy_kwh,   10),
        "duration_s":   round(duration_s,    2),
        "returncode":   returncode,
        "exit_status":  traj["exit_status"],
        "steps":        traj["steps"],
        "code_changed": actually_changed,
        "valid_syntax": valid_syntax,
        "model":        MODEL_NAME,
    }


# ------------------------------------------------------------------
# Main
# ------------------------------------------------------------------
if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--only", nargs="+", metavar="TASK_ID",
        help="Run only these task IDs (space-separated)"
    )
    parser.add_argument(
        "--runs", type=int, default=N_RUNS,
        help=f"Runs per condition (default {N_RUNS})"
    )
    args = parser.parse_args()
    n_runs = args.runs

    print("Pre-flight check: is Ollama running and model available?")
    check = subprocess.run(["ollama", "list"], capture_output=True, text=True)
    model_tag = MODEL_NAME.replace("ollama/", "")
    if model_tag not in check.stdout:
        print(f"\n  WARNING: '{model_tag}' not found in `ollama list`.")
        print(f"  Run:  ollama pull {model_tag.split(':')[0]}")
        print(f"  Then re-run this script.\n")
        raise SystemExit(1)
    print(f"  OK — {model_tag} found.\n")

    ensure_results_dirs()
    done = load_existing_runs()

    tasks = all_task_ids()
    if args.only:
        tasks = [t for t in tasks if t in args.only]
        if not tasks:
            print(f"ERROR: no tasks matched {args.only}")
            raise SystemExit(1)

    total_planned = len(tasks) * len(CONDITIONS) * n_runs
    print("=" * 70)
    print(f"Full Systematic Debug Skill — pilot")
    print(f"Model  : {MODEL_NAME}")
    print(f"Tasks  : {len(tasks)}")
    print(f"Conds  : {' | '.join(CONDITIONS)}")
    print(f"Runs   : {n_runs} per condition  →  {total_planned} total runs")
    print(f"Output : {RESULTS_CSV}")
    print("=" * 70)

    for task_id in tasks:
        meta    = get_task_meta(task_id)
        problem = meta.get("problem_statement", "")
        if not problem:
            print(f"  [ERROR] No problem_statement found for {task_id} — skipping.")
            continue

        print(f"\n{'='*70}")
        print(f"TASK : {task_id}")
        print(f"{'='*70}")

        for condition in CONDITIONS:
            pending = [
                r for r in range(1, n_runs + 1)
                if (task_id, condition, str(r)) not in done
            ]
            if not pending:
                print(f"  [{condition}] already complete, skipping.")
                continue

            print(f"\n  Running [{condition}] — pending runs: {pending}")
            for i in pending:
                print(f"    run {i}/{n_runs}...", end=" ", flush=True)
                r = run_once(task_id, problem, condition, run_index=i)
                append_result(r)
                done.add((task_id, condition, str(i)))
                print(f"energy={r['energy_kwh']:.8f} kWh  "
                      f"duration={r['duration_s']:.1f}s  "
                      f"changed={r['code_changed']}  status={r['exit_status']}")

    print("\n" + "=" * 70)
    print(f"Done. Results saved to: {RESULTS_CSV}")
    print("Next: python3 evaluate_patches_full_debug.py")
    print("=" * 70)

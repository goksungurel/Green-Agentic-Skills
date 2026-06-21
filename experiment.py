"""
experiment.py
-------------
Runs SWE-bench tasks under three conditions:

1. baseline           — no skill injected
2. general_skill      — skill.md (general guidance) prepended
3. debug_skill        — skills/debugging_skill.md prepended
4. feature_skill      — skills/feature_skill.md prepended

For each run the target repo is cloned at the task's base commit into a
temp directory, the agent runs inside that directory, and the temp
directory is deleted afterwards.

All results are appended to results/runs.csv
Trajectory JSONs are saved to results/trajectories/
"""

import csv
import os
import shutil
import subprocess
import tempfile
from datetime import datetime

from codecarbon import EmissionsTracker

# ------------------------------------------------------------------
# Configuration
# ------------------------------------------------------------------
N_RUNS      = 3
MAX_STEPS   = 10
TIMEOUT     = 800
RESULTS_CSV = "results/runs.csv"
TRAJ_DIR    = "results/trajectories"
TASKS_CSV   = "selected_tasks.csv"

# Absolute paths so they work regardless of cwd inside subprocess
_HERE      = os.path.dirname(os.path.abspath(__file__))
MINI_YAML  = os.path.join(_HERE, "mini.yaml")

SKILL_FILES = {
    "baseline":      None,
    "debug_skill":   os.path.join(_HERE, "skills", "debugging_skill.md"),
    "feature_skill": os.path.join(_HERE, "skills", "feature_skill.md"),
}

CSV_HEADERS = [
    "timestamp", "task_id", "condition", "run",
    "emissions_kg", "energy_kwh", "duration_s",
    "returncode", "exit_status", "steps", "success"
]

# ------------------------------------------------------------------
# Task metadata
# ------------------------------------------------------------------
_TASK_META: dict | None = None


def _load_task_meta() -> dict:
    meta = {}
    with open(TASKS_CSV, newline="") as f:
        for row in csv.DictReader(f):
            meta[row["instance_id"]] = {
                "repo":   row["repo"],
                "commit": row["base_commit"],
            }
    return meta


def get_task_meta(task_id: str) -> dict:
    global _TASK_META
    if _TASK_META is None:
        _TASK_META = _load_task_meta()
    return _TASK_META.get(task_id, {})


# ------------------------------------------------------------------
# Repo cloning
# ------------------------------------------------------------------
def clone_repo(repo: str, commit: str) -> str:
    """Clone repo at specific commit into a fresh temp dir. Returns the path."""
    tmpdir = tempfile.mkdtemp(prefix="greenskill_")
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


# ------------------------------------------------------------------
# Trajectory parsing
# ------------------------------------------------------------------
def parse_trajectory(traj_file: str) -> dict:
    """
    Extract exit_status and step count from a trajectory JSON.
    Returns {"exit_status": str, "steps": int} or defaults if file missing.
    """
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


# ------------------------------------------------------------------
# Results helpers
# ------------------------------------------------------------------
def ensure_results_dir():
    os.makedirs(TRAJ_DIR, exist_ok=True)
    if not os.path.exists(RESULTS_CSV):
        with open(RESULTS_CSV, "w", newline="") as f:
            csv.DictWriter(f, fieldnames=CSV_HEADERS).writeheader()


def append_result(row: dict):
    with open(RESULTS_CSV, "a", newline="") as f:
        csv.DictWriter(f, fieldnames=CSV_HEADERS).writerow(row)


# ------------------------------------------------------------------
# Core run
# ------------------------------------------------------------------
def run_once(task_id: str, problem_statement: str,
             condition: str, run_index: int) -> dict:
    """
    Clone the task repo, run mini-swe-agent inside it, measure energy.
    The cloned directory is always deleted after the run.
    """
    skill_file = SKILL_FILES.get(condition)
    if skill_file:
        prompt = open(skill_file).read() + f"\n\n---\n\nTASK: {problem_statement}"
    else:
        prompt = problem_statement

    prompt_file = f"/tmp/greenskill_{task_id}_{condition}_run{run_index}.txt"
    with open(prompt_file, "w") as f:
        f.write(prompt)

    traj_file = os.path.join(
        _HERE, TRAJ_DIR, f"{task_id}__{condition}__run{run_index}.json"
    )

    meta   = get_task_meta(task_id)
    repo   = meta.get("repo")
    commit = meta.get("commit")

    tracker = EmissionsTracker(
        project_name=f"{task_id}_{condition}_run{run_index}",
        output_dir="results",
        log_level="error",
        save_to_file=False,
    )
    tracker.start()
    start_time = datetime.now()

    env = os.environ.copy()
    env["MSWEA_COST_TRACKING"] = "ignore_errors"

    timed_out  = False
    returncode = -1
    repo_dir   = None

    try:
        if repo and commit:
            repo_dir = clone_repo(repo, commit)

        result = subprocess.run(
            [
                "bash", "-c",
                f"mini-swe-agent "
                f"--model ollama/qwen2.5-coder:7b "
                f'--task "$(cat {prompt_file})" '
                f"--yolo "
                f"--exit-immediately "
                f"-c {MINI_YAML} "
                f"-c agent.max_steps={MAX_STEPS} "
                f"-o {traj_file}"
            ],
            capture_output=True, text=True,
            timeout=TIMEOUT, env=env,
            cwd=repo_dir,
        )
        returncode = result.returncode

    except subprocess.TimeoutExpired:
        timed_out = True
        print(f"    [TIMEOUT] run {run_index} exceeded {TIMEOUT}s")

    finally:
        if repo_dir:
            shutil.rmtree(repo_dir, ignore_errors=True)

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
    submitted = traj["exit_status"] == "Submitted"

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
        "success":      (not timed_out) and submitted,
    }


def run_condition(task_id: str, problem_statement: str,
                  condition: str, n_runs: int = N_RUNS) -> dict:
    """Run a task N times under one condition, save rows, return averages."""
    print(f"\n  Running {n_runs}x [{condition}]...")
    results = []
    for i in range(1, n_runs + 1):
        print(f"    run {i}/{n_runs}...", end=" ", flush=True)
        r = run_once(task_id, problem_statement, condition, run_index=i)
        results.append(r)
        append_result(r)
        print(f"energy={r['energy_kwh']:.8f} kWh  "
              f"duration={r['duration_s']:.1f}s  "
              f"success={r['success']}")

    valid  = [r for r in results if r["success"] and r["emissions_kg"] > 0]
    n_valid = len(valid)
    avg = lambda key: sum(r[key] for r in valid) / n_valid if valid else 0.0

    print(f"  --> avg energy   : {avg('energy_kwh'):.8f} kWh")
    print(f"  --> avg duration : {avg('duration_s'):.1f} s")
    print(f"  --> success rate : {len([r for r in results if r['success']])}/{n_runs}")

    return {
        "task_id":       task_id,
        "condition":     condition,
        "avg_emissions": avg("emissions_kg"),
        "avg_energy":    avg("energy_kwh"),
        "avg_duration":  avg("duration_s"),
        "n_valid":       n_valid,
    }


if __name__ == "__main__":
    ensure_results_dir()

    task_id = "astropy__astropy-12907"
    problem = (
        "Modeling's separability_matrix does not compute separability correctly "
        "for nested CompoundModels. The function returns wrong results when models "
        "are composed together using the & operator."
    )

    print("=" * 60)
    print(f"Task  : {task_id}")
    print(f"Runs  : {N_RUNS} per condition")
    print("=" * 60)

    results = {}
    for cond in ["baseline", "debug_skill"]:
        results[cond] = run_condition(task_id, problem, condition=cond)

    print("\n" + "=" * 60)
    print("COMPARISON")
    print("=" * 60)
    b = results["baseline"]["avg_energy"]
    e = results["debug_skill"]["avg_energy"]
    if b > 0 and e > 0:
        delta = (e - b) / b * 100
        print(f"  debug_skill: {e:.8f} kWh  "
              f"({abs(delta):.1f}% {'LESS' if delta < 0 else 'MORE'} than baseline)")
    print("=" * 60)

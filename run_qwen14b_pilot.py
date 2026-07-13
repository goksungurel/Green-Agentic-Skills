"""
run_qwen14b_pilot.py
--------------------
Isolated 14B pilot — 3 tasks × 2 conditions × 3 runs = 18 runs.

Model  : ollama/qwen2.5-coder:14b
         NOTE: requires `ollama pull qwen2.5-coder:14b` before running.
         If RAM is tight on M2 16GB, create a custom model with smaller
         context (e.g. 16k) instead of the default 32k:
           echo 'FROM qwen2.5-coder:14b\nPARAMETER num_ctx 16384' | ollama create qwen14b-16k -
         Then change MODEL_NAME below to "ollama/qwen14b-16k".

Tasks  :
  - psf__requests-2317   (known-resolved in 7B)   → logic_debug_skill
  - psf__requests-2148   (consistently unresolved) → exception_debug_skill
  - django__django-11039 (representative django)   → logic_debug_skill

Outputs:
  results/runs_14b.csv
  results/trajectories_14b/
  results/patches_14b/

The 7B pipeline (experiment.py / results/runs.csv) is NOT touched.
"""

import csv
import os
import shutil
import subprocess
import tempfile
from datetime import datetime

from codecarbon import EmissionsTracker

# ------------------------------------------------------------------
# Configuration  — only change MODEL_NAME if you renamed the Ollama model
# ------------------------------------------------------------------
MODEL_NAME  = "ollama/qwen2.5-coder:14b"
N_RUNS      = 5
MAX_STEPS   = 25
TIMEOUT     = 1200

RESULTS_CSV = "results/runs_14b.csv"
TRAJ_DIR    = "results/trajectories_14b"
PATCH_DIR   = "results/patches_14b"
TASKS_CSV   = "selected_tasks.csv"

_HERE       = os.path.dirname(os.path.abspath(__file__))
MINI_YAML   = os.path.join(_HERE, "mini.yaml")
LOCAL_REPOS = os.path.join(_HERE, "repos")

SKILL_FILES = {
    "baseline":              None,
    "exception_debug_skill": os.path.join(_HERE, "skills", "exception_debug_skill.md"),
    "logic_debug_skill":     os.path.join(_HERE, "skills", "logic_debug_skill.md"),
    "feature_skill":         os.path.join(_HERE, "skills", "feature_skill.md"),
}

# (task_id, skill_condition_to_use_for_that_task)
PILOT_TASKS = [
    ("psf__requests-2317",   "logic_debug_skill"),
    ("psf__requests-2148",   "exception_debug_skill"),
    ("django__django-11039", "logic_debug_skill"),
]

CSV_HEADERS = [
    "timestamp", "task_id", "condition", "run",
    "emissions_kg", "energy_kwh", "duration_s",
    "returncode", "exit_status", "steps", "code_changed", "valid_syntax",
    "model",
]


# ------------------------------------------------------------------
# Helpers (copied from experiment.py — do not import from there to
# keep this script fully self-contained and the 7B run untouched)
# ------------------------------------------------------------------

def build_prompt(skill_file, problem_statement):
    if skill_file and os.path.isfile(skill_file):
        with open(skill_file) as f:
            return f.read() + "\n\n---\n\n" + problem_statement
    return problem_statement


_TASK_META = None

def _load_task_meta():
    meta = {}
    with open(os.path.join(_HERE, TASKS_CSV), newline="") as f:
        for row in csv.DictReader(f):
            meta[row["instance_id"]] = {
                "repo":              row["repo"],
                "commit":            row["base_commit"],
                "problem_statement": row["problem_statement"],
            }
    return meta

def get_task_meta(task_id):
    global _TASK_META
    if _TASK_META is None:
        _TASK_META = _load_task_meta()
    return _TASK_META.get(task_id, {})


def clone_repo(repo, commit):
    tmpdir = tempfile.mkdtemp(prefix="greenskill14b_")
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


def append_result(row):
    csv_path = os.path.join(_HERE, RESULTS_CSV)
    with open(csv_path, "a", newline="") as f:
        csv.DictWriter(f, fieldnames=CSV_HEADERS).writerow(row)


# ------------------------------------------------------------------
# Core run
# ------------------------------------------------------------------

def run_once(task_id, problem_statement, condition, run_index):
    skill_file = SKILL_FILES.get(condition)
    prompt     = build_prompt(skill_file, problem_statement)

    prompt_file = f"/tmp/greenskill14b_{task_id}_{condition}_run{run_index}.txt"
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
        project_name=f"14b_{task_id}_{condition}_run{run_index}",
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

    try:
        if repo and commit:
            repo_dir = clone_repo(repo, commit)

        result = subprocess.run(
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
            capture_output=True, text=True,
            timeout=TIMEOUT, env=env,
            cwd=repo_dir,
        )
        returncode = result.returncode

    except subprocess.TimeoutExpired:
        timed_out = True
        print(f"    [TIMEOUT] run {run_index} exceeded {TIMEOUT}s")

    finally:
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


def run_condition(task_id, problem_statement, condition):
    print(f"\n  [{condition}]")
    results = []
    for i in range(1, N_RUNS + 1):
        print(f"    run {i}/{N_RUNS}...", end=" ", flush=True)
        r = run_once(task_id, problem_statement, condition, run_index=i)
        results.append(r)
        append_result(r)
        print(f"energy={r['energy_kwh']:.8f} kWh  "
              f"dur={r['duration_s']:.0f}s  "
              f"changed={r['code_changed']}  "
              f"status={r['exit_status']}")

    measured  = [r for r in results if r["energy_kwh"] > 0]
    n_m       = len(measured)
    avg       = lambda k: sum(r[k] for r in measured) / n_m if n_m else 0.0
    n_changed = sum(1 for r in results if r["code_changed"])
    print(f"  --> avg energy  : {avg('energy_kwh'):.8f} kWh")
    print(f"  --> avg steps   : {avg('steps'):.1f}")
    print(f"  --> code_changed: {n_changed}/{N_RUNS}")
    return results


# ------------------------------------------------------------------
# Main
# ------------------------------------------------------------------
if __name__ == "__main__":
    print("=" * 65)
    print(f"GreenSkill — 14B Pilot")
    print(f"Model  : {MODEL_NAME}")
    print(f"Runs   : {N_RUNS} per condition")
    print(f"Tasks  : {len(PILOT_TASKS)}")
    print(f"Output : {RESULTS_CSV}")
    print("=" * 65)
    print()
    print("Pre-flight check: is Ollama running and model available?")
    check = subprocess.run(["ollama", "list"], capture_output=True, text=True)
    model_tag = MODEL_NAME.replace("ollama/", "")
    if model_tag not in check.stdout:
        print(f"\n  WARNING: '{model_tag}' not found in `ollama list`.")
        print(f"  Run:  ollama pull {model_tag}")
        print(f"  Then re-run this script.\n")
        raise SystemExit(1)
    print(f"  OK — {model_tag} found.\n")

    ensure_results_dirs()

    all_results = []
    for task_id, skill_cond in PILOT_TASKS:
        meta = get_task_meta(task_id)
        problem = meta.get("problem_statement", "")
        print("=" * 65)
        print(f"Task: {task_id}  (skill: {skill_cond})")
        print("=" * 65)
        for cond in ["baseline", skill_cond]:
            rows = run_condition(task_id, problem, cond)
            all_results.extend(rows)

    # ------------------------------------------------------------------
    # Summary
    # ------------------------------------------------------------------
    print("\n" + "=" * 65)
    print("PILOT SUMMARY  (energy in milli-kWh)")
    print("=" * 65)
    print(f"{'Task':<28} {'Condition':<24} {'mWh':>8}  {'Steps':>6}  {'Changed'}")
    print("-" * 65)
    for task_id, skill_cond in PILOT_TASKS:
        for cond in ["baseline", skill_cond]:
            rows = [r for r in all_results
                    if r["task_id"] == task_id and r["condition"] == cond]
            measured = [r for r in rows if r["energy_kwh"] > 0]
            n_m = len(measured)
            avg_e = sum(r["energy_kwh"] for r in measured) / n_m * 1000 if n_m else 0
            avg_s = sum(r["steps"] for r in measured) / n_m if n_m else 0
            n_ch  = sum(1 for r in rows if r["code_changed"])
            print(f"  {task_id:<26} {cond:<24} {avg_e:>8.3f}  {avg_s:>6.1f}  {n_ch}/{N_RUNS}")
    print("=" * 65)
    print(f"\nResults saved to: {RESULTS_CSV}")
    print("Next step: run evaluate_patches_14b.py to get accuracy numbers.")

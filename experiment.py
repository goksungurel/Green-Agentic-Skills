"""
experiment.py
-------------
Runs a single SWE-bench task N_RUNS times for both conditions:

1. Baseline   — no skill injected into the prompt
2. With Skill — skill.md injected at the beginning of the prompt

All results are appended to a single CSV file: results/runs.csv
Trajectory JSONs are saved to: results/trajectories/

Why a single CSV?
    With 30 tasks x 10 runs x 2 conditions = 600 runs,
    having one file per run would create 600 files.
    A single CSV makes analysis much easier.
"""

import os
import csv
import subprocess
from datetime import datetime
from codecarbon import EmissionsTracker

# ------------------------------------------------------------------
# Configuration
# ------------------------------------------------------------------
N_RUNS       = 10        # number of times to run each condition per task
MAX_STEPS    = 10       # max agent steps per run
TIMEOUT      = 800      # seconds before giving up on a run
RESULTS_CSV  = "results/runs.csv"
TRAJ_DIR     = "results/trajectories"

# CSV column headers
CSV_HEADERS = [
    "timestamp", "task_id", "condition", "run",
    "emissions_kg", "energy_kwh", "duration_s",
    "returncode", "success"
]


def ensure_results_dir():
    """Create results directories and CSV header if they don't exist."""
    os.makedirs(TRAJ_DIR, exist_ok=True)

    # Create CSV with headers if it doesn't exist yet
    if not os.path.exists(RESULTS_CSV):
        with open(RESULTS_CSV, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=CSV_HEADERS)
            writer.writeheader()


def append_result(row: dict):
    """Append one run's result as a new row in runs.csv."""
    with open(RESULTS_CSV, "a", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_HEADERS)
        writer.writerow(row)


def run_once(task_id: str, problem_statement: str,
             use_skill: bool, run_index: int) -> dict:
    """
    Run mini-swe-agent once on a task and measure energy.

    Parameters
    ----------
    task_id           : unique task identifier (e.g. 'astropy__astropy-12907')
    problem_statement : the bug description given to the agent
    use_skill         : if True, prepend skill.md content to the prompt
    run_index         : which run this is (1, 2, 3, ...)

    Returns
    -------
    dict with all measured metrics
    """
    condition = "with_skill" if use_skill else "baseline"

    # --- Build the prompt ---
    if use_skill:
        skill_text = open("skill.md").read()
        prompt = f"{skill_text}\n\n---\n\nTASK: {problem_statement}"
    else:
        prompt = problem_statement

    # Write prompt to a temp file to avoid shell escaping issues
    prompt_file = f"/tmp/greenskill_{task_id}_{condition}_run{run_index}.txt"
    with open(prompt_file, "w") as f:
        f.write(prompt)

    # Trajectory output path
    traj_file = f"{TRAJ_DIR}/{task_id}__{condition}__run{run_index}.json"

    # --- Start energy measurement ---
    tracker = EmissionsTracker(
        project_name=f"{task_id}_{condition}_run{run_index}",
        output_dir="results",          # CodeCarbon internal log (we ignore this)
        log_level="error",
        save_to_file=False,            # we handle our own CSV
    )
    tracker.start()
    start_time = datetime.now()

    # --- Run the agent ---
    env = os.environ.copy()
    env['MSWEA_COST_TRACKING'] = 'ignore_errors'

    timed_out = False
    returncode = -1
    try:
        result = subprocess.run(
            [
                "bash", "-c",
                f'mini-swe-agent '
                f'--model ollama/qwen2.5-coder:7b '
                f'--task "$(cat {prompt_file})" '
                f'--yolo '
                f'--exit-immediately '
                f'-c mini.yaml '
                f'-c agent.max_steps={MAX_STEPS} '
                f'-o {traj_file}'
            ],
            capture_output=True,
            text=True,
            timeout=TIMEOUT,
            env=env
        )
        returncode = result.returncode
    except subprocess.TimeoutExpired:
        timed_out = True
        print(f"    [TIMEOUT] run {run_index} exceeded {TIMEOUT}s, skipping")

    # --- Stop energy measurement ---
    emissions_kg = tracker.stop() or 0.0
    duration_s   = (datetime.now() - start_time).total_seconds()

    # Get energy in kWh from tracker
    try:
        energy_kwh = tracker._total_energy.kWh
    except Exception:
        energy_kwh = 0.0

    if timed_out:
        emissions_kg = 0.0
        energy_kwh   = 0.0

    success = (not timed_out) and (returncode == 0)

    return {
        "timestamp":    datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "task_id":      task_id,
        "condition":    condition,
        "run":          run_index,
        "emissions_kg": round(emissions_kg, 10),
        "energy_kwh":   round(energy_kwh,   10),
        "duration_s":   round(duration_s,    2),
        "returncode":   returncode,
        "success":      success,
    }


def run_task_with_average(task_id: str, problem_statement: str,
                          use_skill: bool, n_runs: int = N_RUNS) -> dict:
    """
    Run a task N times, save each result to runs.csv, return averages.
    """
    condition = "with_skill" if use_skill else "baseline"
    print(f"\n  Running {n_runs}x [{condition}]...")

    results = []
    for i in range(1, n_runs + 1):
        print(f"    run {i}/{n_runs}...", end=" ", flush=True)
        r = run_once(task_id, problem_statement, use_skill, run_index=i)
        results.append(r)
        append_result(r)   # save to runs.csv immediately
        print(f"emissions={r['emissions_kg']:.8f} kg  "
              f"energy={r['energy_kwh']:.8f} kWh  "
              f"duration={r['duration_s']:.1f}s  "
              f"success={r['success']}")

    # Average over valid (successful, non-zero) runs only
    valid = [r for r in results if r['success'] and r['emissions_kg'] > 0]
    n_valid = len(valid)

    avg_emissions = sum(r['emissions_kg'] for r in valid) / n_valid if valid else 0.0
    avg_energy    = sum(r['energy_kwh']   for r in valid) / n_valid if valid else 0.0
    avg_duration  = sum(r['duration_s']   for r in valid) / n_valid if valid else 0.0
    success_rate  = sum(1 for r in results if r['success']) / len(results)

    print(f"  --> avg emissions : {avg_emissions:.8f} kg CO2")
    print(f"  --> avg energy    : {avg_energy:.8f} kWh")
    print(f"  --> avg duration  : {avg_duration:.1f} s")
    print(f"  --> success rate  : {success_rate*100:.0f}% ({n_valid}/{n_runs} valid)")

    return {
        "task_id":        task_id,
        "condition":      condition,
        "avg_emissions":  avg_emissions,
        "avg_energy":     avg_energy,
        "avg_duration":   avg_duration,
        "success_rate":   success_rate,
        "n_valid":        n_valid,
    }


if __name__ == "__main__":
    ensure_results_dir()

    # ------------------------------------------------------------------
    # Week 1 goal: single task, N_RUNS per condition
    # ------------------------------------------------------------------
    task_id = "astropy__astropy-12907"
    problem = (
        "Modeling's `separability_matrix` does not compute separability correctly "
        "for nested CompoundModels. The function returns wrong results when models "
        "are composed together using the & operator."
    )

    print("=" * 60)
    print(f"Task  : {task_id}")
    print(f"Runs  : {N_RUNS} per condition")
    print(f"Output: {RESULTS_CSV}")
    print("=" * 60)

    baseline = run_task_with_average(task_id, problem, use_skill=False)
    skill    = run_task_with_average(task_id, problem, use_skill=True)

    print("\n" + "=" * 60)
    print("FINAL COMPARISON (averages over valid runs)")
    print("=" * 60)
    b_e = baseline['avg_emissions']
    s_e = skill['avg_emissions']
    b_k = baseline['avg_energy']
    s_k = skill['avg_energy']

    if b_e > 0 and s_e > 0:
        change_e = (s_e - b_e) / b_e * 100
        change_k = (s_k - b_k) / b_k * 100 if b_k > 0 else 0
        dir_e = "LESS" if change_e < 0 else "MORE"
        dir_k = "LESS" if change_k < 0 else "MORE"
        print(f"  Emissions  — baseline: {b_e:.8f} kg  |  skill: {s_e:.8f} kg  "
            f"→ {abs(change_e):.1f}% {dir_e}")
        print(f"  Energy     — baseline: {b_k:.8f} kWh |  skill: {s_k:.8f} kWh "
            f"→ {abs(change_k):.1f}% {dir_k}")
    else:
        print("  Not enough valid runs to compare.")

    print(f"\n  All results saved to: {RESULTS_CSV}")
    print("=" * 60)

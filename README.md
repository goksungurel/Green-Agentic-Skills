# GreenSkill — Does Structured Guidance Reduce AI Energy Consumption?

**Research Question:**
Does injecting a task-specific skill file into an AI coding agent's prompt reduce the energy it consumes when solving software engineering tasks?

**Hypothesis:**
Structured guidance reduces unproductive agent turns → fewer LLM calls → less energy consumed per solved task.

---

## Overview

GreenSkill is an empirical study that runs a fully local AI coding agent on [SWE-bench Lite](https://www.swebench.com/lite.html) tasks under two conditions and measures energy consumption. Each task receives either no skill (baseline) or a task-specific skill file matched to the bug type. By comparing energy, step count, and success rate across conditions, we test whether skill injection is a viable Green AI strategy.

---

## System Components

| Component | Tool |
|---|---|
| Agent | [mini-SWE-agent](https://github.com/SWE-agent/mini-swe-agent) v2.4.1 |
| Model | Qwen2.5-Coder-7B via Ollama (fully local, no internet during runs) |
| Benchmark | SWE-bench Lite — 30 tasks across 7 repositories |
| Energy measurement | [CodeCarbon](https://github.com/mlco2/codecarbon) |
| Hardware | Apple Silicon M2 Air, 16GB RAM |

---

## Experiment Design

**30 tasks × 2 conditions × 5 runs = 300 total runs**

Each task has exactly 2 conditions: `baseline` and one task-specific skill condition.

| Condition | What the agent receives |
|---|---|
| `baseline` | Problem statement only |
| `task_specific_skill` | Task-specific skill file + problem statement |

Task type determines which skill file is injected:
- **Exception debug tasks (7)** — bugs with a clear exception/traceback → `skills/exception_debug_skill.md`
- **Logic debug tasks (13)** — silent/wrong-result bugs, no exception → `skills/logic_debug_skill.md`
- **Feature tasks (10)** — requests to add new functionality → `skills/feature_skill.md`

Skill files are adapted from the **[systematic-debugging](https://www.skillhub.club/)** skill by @obra (SkillHub S9.2 rated). Each file is a concise bug pattern table (~27 lines) that adds domain knowledge without duplicating the agent's built-in workflow.

### Model Configuration

| Parameter | Value |
|---|---|
| Model | `ollama/qwen2.5-coder:7b-32k` (num_ctx=32768 explicit) |
| Temperature | `0.2` (low but non-zero — controlled reproducibility) |
| Time limit | 120s per step |
| Max steps | 25 |
| Timeout | 1200s per run |

### Outcome Metrics Per Run

A run is **submitted** when `exit_status == Submitted`. A submitted run is further classified by:
- `code_changed == True` — agent actually modified a file (verified via `git diff HEAD`)
- `valid_syntax == True` — every changed `.py` file passes `py_compile` (catches broken patches the agent never verified)

Runs where the agent hit the step limit without submitting are recorded as `LimitsExceeded`. Runs aborted by the dedup guard (see `dedup_agent.py`) are recorded as `StuckRepetition`.

### Accuracy Metric

Patches are evaluated with the SWE-bench Docker harness (`evaluate_patches.py`). A patch is **resolved** if all FAIL_TO_PASS tests pass and no PASS_TO_PASS tests regress.

### Metrics Recorded Per Run

| Metric | Description |
|---|---|
| `energy_kwh` | Energy consumed (kWh), measured by CodeCarbon |
| `steps` | Number of LLM calls the agent made |
| `exit_status` | `Submitted`, `LimitsExceeded`, `StuckRepetition`, or `RepeatedFormatError` |
| `code_changed` | `True` if agent modified at least one file |
| `valid_syntax` | `True` / `False` if code changed; `n/a` if no file was modified |
| `duration_s` | Wall-clock time in seconds |

---

## Project Structure

```
greenskill/
├── experiment.py          # Core pipeline: clone repo → run agent → measure energy → save patch
├── dedup_agent.py         # Harness-level guard: intercepts stuck repetition loops, blocks empty-diff submits
├── run_batch.py           # Batch runner: 30 tasks × 2 conditions × 5 runs = 300 runs, resumes if interrupted
├── evaluate_patches.py    # Runs SWE-bench harness on saved patches → writes accuracy.csv
├── analyze.py             # Reads runs.csv + accuracy.csv, prints tables, saves figures
├── select_tasks.py        # One-time: selects 30 tasks from SWE-bench Lite
├── mini.yaml              # Agent config: system prompt, workflow, temperature, time limit
├── start_pilot.sh         # Run a small pilot batch
├── start_validation.sh    # Run validation suite (blueprint/placeholder fix checks)
├── start_validation_dedup.sh  # Run validation suite for dedup guard
├── start_validation_v2.sh     # Run round-2 validation suite
├── validate_blueprint_fix.py  # Check blueprint/placeholder bug recurrence
├── validate_dedup_fix.py      # Check dedup guard behavior
├── validate_fixes_v2.py       # Round-2 validation checker
├── skills/
│   ├── exception_debug_skill.md  # Bug patterns for exceptions/tracebacks
│   ├── logic_debug_skill.md      # Bug patterns for silent/wrong-result bugs
│   └── feature_skill.md          # Patterns for feature addition tasks
├── selected_tasks.csv     # 30 selected tasks (instance_id, repo, commit, problem)
├── repos/                 # Local git mirrors for offline operation (not committed)
└── results/
    ├── runs.csv           # All experiment results (one row per run)
    ├── accuracy.csv       # Harness evaluation results (one row per patch)
    ├── trajectories/      # Full agent JSON trajectories (one file per run)
    ├── patches/           # Git diffs saved as .patch files
    └── figures/           # Bar charts generated by analyze.py
```

---

## How to Run

```bash
# Activate environment
source venv/bin/activate

# Start full batch (300 runs)
python3 run_batch.py

# Monitor progress
tail -f results/batch_run.log

# Evaluate patches with SWE-bench harness (run after batch completes)
python3 evaluate_patches.py

# Analyze results and generate figures
python3 analyze.py
```

---

## Results Schema

### runs.csv
```
timestamp, task_id, condition, run,
emissions_kg, energy_kwh, duration_s,
returncode, exit_status, steps, code_changed, valid_syntax
```
Rows with `energy_kwh == 0` represent timed-out or measurement-failed runs and are excluded from energy averages in `analyze.py`.

### accuracy.csv
```
task_id, condition, run, resolved
```
Generated by `evaluate_patches.py` after running the SWE-bench harness.

---

## Repositories Covered

`astropy` · `django` · `matplotlib` · `mwaskom/seaborn` · `pallets/flask` · `psf/requests` · `pydata/xarray`

# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Research Goal

This project tests whether injecting a task-specific skill file into an AI coding agent's prompt reduces energy consumption on SWE-bench tasks. Each task runs under two conditions: **baseline** (no skill) and **task_specific_skill** — one of three skill files chosen by task type: `exception_debug_skill.md`, `logic_debug_skill.md`, or `feature_skill.md`.

## How to Run

```bash
# Activate virtual environment first
source venv/bin/activate

# Start full batch from scratch (archives old results, runs all 300 runs)
./start_batch.sh

# Resume after interruption (continues from where it left off)
./resume_batch.sh

# Monitor progress
tail -f results/batch_run.log

# Analyze results after batch completes
python3 analyze.py
```

## Architecture

**`experiment.py`** is the core pipeline. For each run it:
1. Reads the appropriate skill file (if condition != baseline) and writes a prompt to `/tmp/`
2. Clones the task repo at the correct commit from `repos/` (local mirrors, works offline)
3. Wraps `mini-swe-agent` with `EmissionsTracker` from CodeCarbon
4. After the agent finishes, runs `git diff HEAD --name-only` to check for real file changes
5. Appends one row per run to `results/runs.csv` and saves the trajectory JSON

**`run_batch.py`** iterates over all 30 tasks × 2 conditions × 5 runs = 300 total runs.
Resume logic: reads existing CSV and skips already-completed (task_id, condition, run) triples.

**`mini.yaml`** configures the agent: system/instance prompt templates, `yolo` mode (no human-in-the-loop), 120s per-step time limit, and `temperature: 0.2` (low but non-zero — reproducible across runs without being fully deterministic).

**`select_tasks.py`** loads SWE-bench Lite from Hugging Face and deterministically picks 30 tasks across 7 repos into `selected_tasks.csv`.

**`skills/`** holds the three active skill files:
- `exception_debug_skill.md` — injected for tasks with a clear exception/traceback (7 tasks)
- `logic_debug_skill.md` — injected for silent/logic bugs with no exception (13 tasks)
- `feature_skill.md` — injected for feature addition tasks (10 tasks)

**`analyze.py`** reads `results/runs.csv` + trajectory JSONs and produces summary tables and figures.

## Key Files

| File | Purpose |
|------|---------|
| `mini.yaml` | Agent configuration (model, temperature, time limit, prompt templates) |
| `skills/exception_debug_skill.md` | Skill for exception-type debug tasks (7 tasks) |
| `skills/logic_debug_skill.md` | Skill for silent/logic bug tasks (13 tasks) |
| `skills/feature_skill.md` | Skill for feature addition tasks (10 tasks) |
| `results/runs.csv` | One row per run — primary data for analysis |
| `results/trajectories/` | Full agent JSON trajectories |
| `selected_tasks.csv` | The 30 SWE-bench tasks for the experiment |
| `repos/` | Local git mirrors for offline operation (not committed) |

## runs.csv Schema

```
timestamp, task_id, condition, run, emissions_kg, energy_kwh, duration_s,
returncode, exit_status, steps, code_changed, success
```

`success` is `True` only when the agent submitted (`exit_status == Submitted`),
made a real file change (`code_changed == True`), and did not time out.
Runs with `energy_kwh == 0` are excluded from energy averages.

## Model Configuration

- **Model:** `ollama/qwen2.5-coder:7b` (fully local, no internet required during runs)
- **Temperature:** `0.2` — set explicitly in `mini.yaml` for controlled reproducibility
- **Step limit:** configured via `agent.max_steps` in `experiment.py`
- **Time limit:** 120s per step

## CodeCarbon Notes

`EmissionsTracker` is initialized with `save_to_file=False`; energy is read back via `tracker._total_energy.kWh`. Measures system-wide energy (not process-isolated). Runs with `energy_kwh == 0` indicate measurement failures and are excluded from analysis.

## Workspace Caution

`results/` must be preserved between runs — `runs.csv` is append-only.
`repos/` contains local git mirrors required for offline operation — do not delete.
`skills/` contains the injection artifacts — deleting these breaks the experiment.

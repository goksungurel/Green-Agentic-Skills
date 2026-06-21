# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Research Goal

This project tests whether injecting a structured `skill.md` file into an AI coding agent's prompt reduces energy consumption on SWE-bench tasks. The two experimental conditions are **baseline** (no skill) and **with_skill** (skill.md prepended to the prompt).

## How to Run

```bash
# Activate virtual environment first
source venv/bin/activate

# One-time: select the 30 benchmark tasks
python3 select_tasks.py

# Run the experiment (appends to results/runs.csv)
export MSWEA_COST_TRACKING='ignore_errors'
python3 experiment.py
```

`experiment.py` currently hardcodes a single task (`astropy__astropy-12907`). To run a different task, edit the `task_id` and `problem` variables in the `__main__` block.

## Architecture

**`experiment.py`** is the core pipeline. For each condition it:
1. Reads `skill.md` (if `use_skill=True`) and writes a prompt to `/tmp/`
2. Wraps a `subprocess.run()` call to `mini-swe-agent` with `EmissionsTracker` from CodeCarbon
3. Appends one row per run to `results/runs.csv` and saves the agent trajectory JSON to `results/trajectories/`

**`mini.yaml`** configures the agent: system/instance prompt templates, `yolo` mode (no human-in-the-loop), Jinja2 observation template, and a 120s per-step time limit. The agent is invoked as `mini-swe-agent --model ollama/qwen2.5-coder:7b`.

**`select_tasks.py`** loads SWE-bench Lite from Hugging Face and deterministically picks 30 tasks across 7 repos into `selected_tasks.csv`.

**`skills/`** directory holds per-task-type skill files. `skill.md` (root-level) is the single skill file currently injected; it must not be deleted between runs.

## Key Files

| File | Purpose |
|------|---------|
| `skill.md` | Skill injected into agent prompt (deleted = experiment breaks) |
| `mini.yaml` | Agent configuration for mini-SWE-agent |
| `results/runs.csv` | One row per run — primary data for analysis |
| `results/trajectories/` | Full agent JSON trajectories |
| `selected_tasks.csv` | The 30 SWE-bench tasks for the full experiment |

## runs.csv Schema

```
timestamp, task_id, condition, run, emissions_kg, energy_kwh, duration_s, returncode, success
```

`success` is `True` only when `returncode == 0` and the run did not time out. Runs with `emissions_kg == 0` are excluded from averages as measurement failures.

## CodeCarbon Notes

`EmissionsTracker` is initialized with `save_to_file=False`; energy is read back via `tracker._total_energy.kWh`. If CodeCarbon cannot find a local energy mix JSON (e.g., for certain country codes), pass `country_iso_code="USA"` explicitly to the `EmissionsTracker` constructor to avoid a crash.

## Workspace Caution

`skill.md` is the injection artifact the experiment depends on. Any `git reset --hard` or workspace cleanup must explicitly exclude `skill.md` and the `skills/` directory. The `results/` directory must also be preserved between runs since `runs.csv` is append-only.

# GreenSkill — Does Structured Guidance Reduce AI Energy Consumption?

**Research Question:**
Does injecting a task-specific skill file into an AI coding agent's prompt reduce the energy it consumes when solving software engineering tasks?

**Hypothesis:**
Structured guidance reduces unproductive agent turns → fewer LLM calls → less energy consumed per solved task.

---

## Research Context

This project was developed as part of a research initiative on **Green Agentic AI** and sustainable software engineering in collaboration with **Wageningen University & Research (WUR)**.

| | |
|---|---|
| **Supervisor** | Dr. June Sallou — Wageningen University & Research |
| **Author** | Göksun Gürel — Izmir University of Economics |

The study was conducted during a Research Internship exploring the boundary between LLM agent prompting strategies and hardware-level energy efficiency.

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
- **Exception debug tasks (10)** — bugs with a clear exception/traceback → `skills/exception_debug_skill.md`
- **Logic debug tasks (11)** — silent/wrong-result bugs, no exception → `skills/logic_debug_skill.md`
- **Feature tasks (9)** — requests to add new functionality → `skills/feature_skill.md`

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

## Results

**300 runs completed** (30 tasks × 2 conditions × 5 runs). Patches evaluated with the SWE-bench Docker harness.

### Accuracy & Energy Summary

| Condition | Runs | Resolved | Energy (avg/run) | vs Baseline | Avg Steps |
|---|---|---|---|---|---|
| Baseline | 149 | **6%** | 0.000302 kWh | — | 13.7 |
| Exception Debug Skill | 50 | 2% | 0.000210 kWh | −30.5% | 14.1 |
| Logic Debug Skill | 52 | 3% | 0.000293 kWh | −2.9% | 16.3 |
| Feature Skill | 45 | **0%** | 0.000347 kWh | +15.1% | 14.3 |

*Energy-All: average over all runs with measured energy (including failed runs).*
*Resolved-only energy is higher for skill conditions where any run resolved: +275% (logic) and +50% (exception) vs baseline. Feature skill resolved 0 tasks (n/a).*

### Code Change Rate

| Condition | Runs | Submitted | Code Changed | Valid Syntax |
|---|---|---|---|---|
| Baseline | 150 | 59% | 43% | 75% |
| Exception Debug Skill | 50 | 58% | 34% | 100% |
| Logic Debug Skill | 55 | 42% | 35% | 95% |
| Feature Skill | 45 | 58% | 22% | 90% |

### Skill Design Comparison: Off-the-Shelf vs. Custom Task-Specific

Two skill injection strategies were evaluated across the same 30 tasks and 5 runs per condition:

| Strategy | Skill File(s) | Energy (avg/run) | vs Baseline | Avg Steps | Code Changed | Resolved |
|---|---|---|---|---|---|---|
| **Baseline** | — | 0.000302–0.000341 kWh | — | 13.7–16.5 | 43% | 6–9% |
| **Off-the-shelf** | `full_systematic_debug_skill.md` (single generic file) | 0.000341 kWh | +0.1% | 16.7 | 37% | 2% |
| **Custom task-specific** | 3 files matched to task type | 0.000281 kWh | −6.8% | 14.9 | 31% | 2% |

Both strategies resolve tasks at the same rate (~2%) and neither outperforms baseline (6–9%). The off-the-shelf skill is energy-neutral; the custom skill saves ~7% energy but at the cost of fewer code changes — meaning it fails faster rather than more efficiently. Neither approach translates skill-file guidance into measurably better outcomes at the 7B model scale.

---

### Key Finding

**Skill injection did not improve accuracy at the 7B model scale — it reduced it.**

- All skill conditions resolved fewer tasks than baseline.
- Feature skill resolved 0 of 45 evaluated patches.
- Exception Debug Skill uses 30.5% less energy overall — but this reflects faster failure (lower code-change rate: 34% vs 43% baseline), not greater efficiency on resolved tasks.
- When skill runs do resolve a task, they consume more energy than baseline resolved runs (+50% for exception, +275% for logic).
- Logic Debug Skill's submit rate dropped to 42% vs 59% baseline, while energy savings are minimal (−2.9%).

**Why:** A 7B model cannot simultaneously follow skill template instructions and read the problem statement independently. The skill's search templates anchor the model to a fixed strategy — e.g., searching `grep -rn "def REAL_FUNCTION_NAME"` — regardless of whether that matches the actual issue. In `django__django-11039`, the baseline found and fixed the bug in 4 steps by searching `migration.atomic` (from the issue body); the logic skill ran all 25 steps searching `def sqlmigrate`, which does not exist as a Python function in the repository.

This aligns with the Green AI literature finding that prompt complexity harms small models: adding structured guidance reduces exploratory behaviour and increases step-budget exhaustion.

---

## Methodological Findings

Several prompt and harness bugs were discovered and fixed during development. The most impactful:

- **Literal placeholder copy-paste** — illustrative examples in `mini.yaml` and skill files (e.g. `grep -rn "class Blueprint"`, `/path/to/file.py`) were copied verbatim by the model instead of being substituted with real values. Fixed by replacing all examples with `ALL_CAPS` placeholder names and explicit "do not type this literally" warnings.
- **`sed -i` editing failures** — `\n` in sed replacement is a literal two-character string on macOS, producing invalid Python. All edits now use `python3 -c "open(...).replace(...)"`.
- **Stuck repetition loops** — the model repeated identical shell commands for the full 25-step budget without adapting. Addressed by `dedup_agent.py` (see below).
- **Empty-diff submits** — the model sometimes submitted after a no-op edit. Fixed by a pre-submit `git diff HEAD` guard in `dedup_agent.py`.

### dedup_agent.py — A Harness-Level Guard

`dedup_agent.py` is a subclass of mini-SWE-agent's `DefaultAgent` that adds two guards:

1. **Stuck repetition guard** — if the model issues the exact same command twice in a row and the result is empty or a shell error (returncode ≠ 0), the second execution is suppressed and the model receives a corrective nudge. A third consecutive repeat aborts the run with `exit_status = StuckRepetition` instead of silently burning the remaining step budget.

2. **Empty-diff submit guard** — when the model issues `COMPLETE_TASK_AND_SUBMIT_FINAL_OUTPUT`, the guard runs `git diff HEAD` first. If the diff is empty (no real file change), the submit is blocked and the model is instructed to re-read the file and retry the edit.

The guard is enabled with `USE_DEDUP_AGENT = True` in `experiment.py`. In the final experiment it was **disabled** (`USE_DEDUP_AGENT = False`) because the `returncode ≠ 0 = unproductive` trigger was too aggressive: it aborted recoverable runs early, cutting the submit rate from 34% to 22% without a compensating accuracy gain. The guard design is sound for the stuck-repetition case; the threshold definition needs refinement for production use.

---

## Repositories Covered

`astropy` · `django` · `matplotlib` · `mwaskom/seaborn` · `pallets/flask` · `psf/requests` · `pydata/xarray`

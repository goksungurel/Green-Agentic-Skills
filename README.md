# Green Agentic Skills

**Research Question:** Does adding a structured `skill.md` file to an AI coding agent's prompt reduce its energy consumption when solving software engineering tasks?

This project investigates the energy/accuracy trade-off of skill injection in agentic AI systems, building on prior work in Green Software Engineering and SWE-bench evaluation.

## Setup

| Component | Tool |
|-----------|------|
| Agent | mini-SWE-agent v2.4.1 |
| Model | Qwen2.5-Coder-7B (via Ollama, local) |
| Benchmark | SWE-bench Lite (30 tasks, 7 repositories) |
| Energy measurement | CodeCarbon |
| Hardware | Apple Silicon (M-series), local execution |

## Project Structure

```
greenskill/
├── skill.md              ← Python debugging skill injected into the agent prompt
├── mini.yaml              ← Agent configuration (model, prompt templates, environment)
├── experiment.py           ← Runs a task N times per condition, logs results
├── select_tasks.py         ← Selects 30 diverse tasks from SWE-bench Lite
├── selected_tasks.csv      ← The 30 selected tasks (instance_id, repo, problem_statement)
├── results/
│   ├── runs.csv             ← All experiment runs (one row per run)
│   └── trajectories/        ← Full agent trajectories (one JSON per run)
└── README.md
```

## Experiment Design

Each task is run under two conditions, each repeated multiple times (N=5–10) to account for LLM non-determinism:

1. **Baseline** — agent receives only the bug description
2. **With Skill** — agent receives `skill.md` prepended to the bug description

### Hypothesis
Structured guidance in `skill.md` reduces unproductive agent steps,
which reduces the number of tokens processed,
which reduces energy consumption.

### Metrics (per run)
- `emissions_kg` — carbon emissions estimated by CodeCarbon
- `energy_kwh` — direct energy consumption (kWh)
- `duration_s` — wall-clock time for the agent to complete the task
- `success` — whether the agent completed without error

All runs are appended to a single `results/runs.csv` for easy analysis;
full agent trajectories are stored separately in `results/trajectories/`.

## How to Run

```bash
# Activate virtual environment
source venv/bin/activate

# Select the 30 tasks (only needs to be run once)
python3 select_tasks.py

# Run the experiment (currently configured for a single task, Week 1 validation)
export MSWEA_COST_TRACKING='ignore_errors'
python3 experiment.py
```

Results are appended to `results/runs.csv` and trajectories to `results/trajectories/`.

## Status

- [x] Pipeline set up (mini-SWE-agent + Ollama + CodeCarbon)
- [x] 30 tasks selected (7 repositories: astropy, django, matplotlib, requests, seaborn, flask, xarray)
- [x] Skill injection implemented and validated
- [x] Single-task pilot run (10 repetitions per condition)
- [ ] Full 30-task batch run
- [ ] Statistical analysis across tasks
- [ ] Write-up of findings

## References

- Tripathy, A., Harshit, C. P., & Vaidhyanathan, K. (2026). *SWEnergy: An Empirical Study on Energy Efficiency in Agentic Issue Resolution Frameworks with SLMs*. ACM Conferences.
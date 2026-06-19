# greenskill

**Research Question:** Does adding a `skill.md` file to an AI agent reduce its energy consumption when solving coding tasks?

## Setup

| Component | Tool |
|-----------|------|
| Agent | mini-SWE-agent v2.4.1 |
| Model | Qwen2.5-Coder-7B (via Ollama, local) |
| Benchmark | SWE-bench Lite (30 tasks) |
| Energy measurement | CodeCarbon |

## Project Structure

```
greenskill/
├── skill.md        ← Python debugging skill injected into the agent prompt
├── mini.yaml       ← Agent configuration
├── experiment.py   ← Runs 1 task (baseline + with skill), measures energy
├── results/        ← Trajectory JSONs + emissions CSVs (created on first run)
└── README.md
```

## Experiment Design

Each task is run **twice**:
1. **Baseline** — agent gets only the bug description
2. **With Skill** — agent gets `skill.md` prepended to the bug description

### Hypothesis
Structured guidance in `skill.md` reduces unproductive agent steps
→ fewer tokens processed → lower energy consumption

### Metrics
- Energy (kg CO₂) measured by CodeCarbon
- Number of agent steps (from trajectory JSON)
- Success / failure (returncode)

## How to Run

```bash
# Week 1: single task test
python3 experiment.py
```

Results are saved to `results/`.

"""
analyze.py
----------
Reads results/runs.csv and produces:
  1. Summary table — energy, steps, success rate per condition
  2. Per-task breakdown table
  3. Bar charts saved to results/figures/

Usage:
    python3 analyze.py
"""

import csv
import os
from collections import defaultdict

import matplotlib.pyplot as plt
import numpy as np

CSV      = "results/runs.csv"
FIG_DIR  = "results/figures"

# Conditions shown in the report (in display order)
COND_ORDER  = ["baseline", "debug_skill", "feature_skill"]
COND_LABELS = {
    "baseline":      "Baseline",
    "debug_skill":   "Debug Skill",
    "feature_skill": "Feature Skill",
}
COLORS = {
    "baseline":      "#6c757d",
    "debug_skill":   "#198754",
    "feature_skill": "#fd7e14",
}

# 10 batch tasks and their types
TASK_TYPE = {
    "astropy__astropy-14995":       "debug",
    "mwaskom__seaborn-3190":        "debug",
    "mwaskom__seaborn-3010":        "debug",
    "matplotlib__matplotlib-22711": "debug",
    "matplotlib__matplotlib-22835": "debug",
    "django__django-11001":         "debug",
    "astropy__astropy-6938":        "debug",
    "pallets__flask-4992":          "feature",
    "astropy__astropy-14365":       "feature",
    "django__django-10924":         "feature",
}


# ------------------------------------------------------------------
# Data loading
# ------------------------------------------------------------------
def load_runs(csv_path: str) -> list[dict]:
    with open(csv_path, newline="") as f:
        rows = list(csv.DictReader(f))
    for r in rows:
        r["energy_kwh"]   = float(r["energy_kwh"]   or 0)
        r["emissions_kg"] = float(r["emissions_kg"]  or 0)
        r["duration_s"]   = float(r["duration_s"]    or 0)
        r["steps"]        = int(r["steps"]           or 0)
        r["submitted"]    = r["exit_status"] == "Submitted"
    return rows


def valid(rows: list[dict]) -> list[dict]:
    """Keep only rows where the agent actually submitted and measured energy."""
    return [r for r in rows if r["submitted"] and r["energy_kwh"] > 0]


# ------------------------------------------------------------------
# Aggregation
# ------------------------------------------------------------------
def avg(vals: list) -> float:
    return sum(vals) / len(vals) if vals else 0.0


def stats_by_condition(rows: list[dict]) -> dict:
    """
    Returns dict: condition -> {energy, steps, duration, success_rate, n_total, n_valid}
    Uses only submitted+measured rows for energy/steps averages.
    """
    by_cond = defaultdict(list)
    all_by_cond = defaultdict(list)
    for r in rows:
        all_by_cond[r["condition"]].append(r)
        if r["submitted"] and r["energy_kwh"] > 0:
            by_cond[r["condition"]].append(r)

    result = {}
    for cond in all_by_cond:
        all_r  = all_by_cond[cond]
        good_r = by_cond[cond]
        result[cond] = {
            "energy":       avg([r["energy_kwh"] for r in good_r]),
            "steps":        avg([r["steps"]       for r in good_r]),
            "duration":     avg([r["duration_s"]  for r in good_r]),
            "success_rate": sum(r["submitted"] for r in all_r) / len(all_r),
            "n_total":      len(all_r),
            "n_valid":      len(good_r),
        }
    return result


def stats_by_task(rows: list[dict], condition: str) -> dict:
    """energy and steps per task for a given condition (valid runs only)."""
    result = {}
    for task_id in TASK_TYPE:
        task_rows = [r for r in rows
                     if r["task_id"] == task_id
                     and r["condition"] == condition
                     and r["submitted"] and r["energy_kwh"] > 0]
        result[task_id] = {
            "energy": avg([r["energy_kwh"] for r in task_rows]),
            "steps":  avg([r["steps"]       for r in task_rows]),
            "n":      len(task_rows),
        }
    return result


# ------------------------------------------------------------------
# Console report
# ------------------------------------------------------------------
def print_summary(stats: dict, baseline_key: str = "baseline"):
    b_energy = stats.get(baseline_key, {}).get("energy", 0)
    b_steps  = stats.get(baseline_key, {}).get("steps",  0)

    print("\n" + "=" * 72)
    print("CONDITION SUMMARY")
    print("=" * 72)
    header = f"{'Condition':<18} {'n':>4} {'Energy (kWh)':>14} {'vs base':>9} {'Steps':>7} {'Success':>8}"
    print(header)
    print("-" * 72)

    for cond in COND_ORDER:
        if cond not in stats:
            continue
        s = stats[cond]
        energy_delta = ((s["energy"] - b_energy) / b_energy * 100) if b_energy > 0 else 0
        steps_delta  = ((s["steps"]  - b_steps)  / b_steps  * 100) if b_steps  > 0 else 0
        direction    = "LESS" if energy_delta < 0 else "more"
        delta_str    = f"{abs(energy_delta):.1f}% {direction}" if b_energy > 0 and cond != baseline_key else "—"
        print(
            f"{COND_LABELS[cond]:<18} {s['n_valid']:>4} "
            f"{s['energy']:>14.8f} {delta_str:>9} "
            f"{s['steps']:>7.1f} {s['success_rate']:>7.0%}"
        )

    print("=" * 72)


def print_per_task(rows: list[dict]):
    b_stats  = stats_by_task(rows, "baseline")
    ds_stats = stats_by_task(rows, "debug_skill")
    fs_stats = stats_by_task(rows, "feature_skill")

    print("\n" + "=" * 80)
    print("PER-TASK: baseline vs task_specific_skill  (valid runs only)")
    print("=" * 80)
    print(f"{'Task':<38} {'type':<8} {'B steps':>8} {'S steps':>8} {'B energy':>12} {'S energy':>12}")
    print("-" * 80)
    for task_id, ttype in TASK_TYPE.items():
        short  = task_id.split("__")[1][:35]
        b      = b_stats[task_id]
        s      = ds_stats[task_id] if ttype == "debug" else fs_stats[task_id]
        b_e    = f"{b['energy']:.6f}" if b["n"] else "    n/a "
        s_e    = f"{s['energy']:.6f}" if s["n"] else "    n/a "
        b_s    = f"{b['steps']:.1f}"  if b["n"] else " n/a"
        s_s    = f"{s['steps']:.1f}"  if s["n"] else " n/a"
        print(f"{short:<38} {ttype:<8} {b_s:>8} {s_s:>8} {b_e:>12} {s_e:>12}")
    print("=" * 80)


# ------------------------------------------------------------------
# Figures
# ------------------------------------------------------------------
def plot_energy(stats: dict, out_dir: str):
    conds  = [c for c in COND_ORDER if c in stats and stats[c]["n_valid"] > 0]
    labels = [COND_LABELS[c] for c in conds]
    values = [stats[c]["energy"] * 1000 for c in conds]   # → milli-kWh for readability
    colors = [COLORS[c] for c in conds]

    fig, ax = plt.subplots(figsize=(8, 5))
    bars = ax.bar(labels, values, color=colors, width=0.5, edgecolor="white")

    # value labels on bars
    for bar, val in zip(bars, values):
        ax.text(bar.get_x() + bar.get_width() / 2,
                bar.get_height() + max(values) * 0.01,
                f"{val:.4f}", ha="center", va="bottom", fontsize=9)

    ax.set_ylabel("Average Energy (milli-kWh)")
    ax.set_title("Energy Consumption per Condition\n(submitted runs only)")
    ax.set_ylim(0, max(values) * 1.2)
    ax.spines[["top", "right"]].set_visible(False)
    plt.tight_layout()
    path = os.path.join(out_dir, "energy_by_condition.png")
    plt.savefig(path, dpi=150)
    plt.close()
    print(f"  Saved: {path}")


def plot_steps(stats: dict, out_dir: str):
    conds  = [c for c in COND_ORDER if c in stats and stats[c]["n_valid"] > 0]
    labels = [COND_LABELS[c] for c in conds]
    values = [stats[c]["steps"] for c in conds]
    colors = [COLORS[c] for c in conds]

    fig, ax = plt.subplots(figsize=(8, 5))
    bars = ax.bar(labels, values, color=colors, width=0.5, edgecolor="white")

    for bar, val in zip(bars, values):
        ax.text(bar.get_x() + bar.get_width() / 2,
                bar.get_height() + max(values) * 0.01,
                f"{val:.1f}", ha="center", va="bottom", fontsize=9)

    ax.set_ylabel("Average LLM Calls (steps)")
    ax.set_title("Agent Steps per Condition\n(submitted runs only)")
    ax.set_ylim(0, max(values) * 1.2)
    ax.spines[["top", "right"]].set_visible(False)
    plt.tight_layout()
    path = os.path.join(out_dir, "steps_by_condition.png")
    plt.savefig(path, dpi=150)
    plt.close()
    print(f"  Saved: {path}")


def plot_success_rate(stats: dict, out_dir: str):
    conds  = [c for c in COND_ORDER if c in stats]
    labels = [COND_LABELS[c] for c in conds]
    values = [stats[c]["success_rate"] * 100 for c in conds]
    colors = [COLORS[c] for c in conds]

    fig, ax = plt.subplots(figsize=(8, 5))
    bars = ax.bar(labels, values, color=colors, width=0.5, edgecolor="white")

    for bar, val in zip(bars, values):
        ax.text(bar.get_x() + bar.get_width() / 2,
                bar.get_height() + 1,
                f"{val:.0f}%", ha="center", va="bottom", fontsize=9)

    ax.set_ylabel("Success Rate (%)")
    ax.set_title("Agent Submission Rate per Condition\n(exit_status == Submitted)")
    ax.set_ylim(0, 110)
    ax.spines[["top", "right"]].set_visible(False)
    plt.tight_layout()
    path = os.path.join(out_dir, "success_by_condition.png")
    plt.savefig(path, dpi=150)
    plt.close()
    print(f"  Saved: {path}")


def plot_per_task_steps(rows: list[dict], out_dir: str):
    b_stats  = stats_by_task(rows, "baseline")
    ds_stats = stats_by_task(rows, "debug_skill")
    fs_stats = stats_by_task(rows, "feature_skill")

    def specific(task_id):
        return ds_stats[task_id] if TASK_TYPE[task_id] == "debug" else fs_stats[task_id]

    tasks_with_data = [t for t in TASK_TYPE
                       if b_stats[t]["n"] > 0 and specific(t)["n"] > 0]
    if not tasks_with_data:
        return

    short_names = [t.split("__")[1][:20] for t in tasks_with_data]
    x     = np.arange(len(tasks_with_data))
    width = 0.35

    b_vals = [b_stats[t]["steps"]    for t in tasks_with_data]
    s_vals = [specific(t)["steps"]   for t in tasks_with_data]
    s_colors = [COLORS["debug_skill"] if TASK_TYPE[t] == "debug"
                else COLORS["feature_skill"] for t in tasks_with_data]

    fig, ax = plt.subplots(figsize=(12, 5))
    ax.bar(x - width/2, b_vals, width, label="Baseline",            color=COLORS["baseline"])
    ax.bar(x + width/2, s_vals, width, label="Task-Specific Skill", color=s_colors)

    ax.set_xticks(x)
    ax.set_xticklabels(short_names, rotation=35, ha="right", fontsize=8)
    ax.set_ylabel("Average Steps")
    ax.set_title("Steps per Task: Baseline vs Task-Specific Skill")
    ax.legend()
    ax.spines[["top", "right"]].set_visible(False)
    plt.tight_layout()
    path = os.path.join(out_dir, "steps_per_task.png")
    plt.savefig(path, dpi=150)
    plt.close()
    print(f"  Saved: {path}")


# ------------------------------------------------------------------
# Main
# ------------------------------------------------------------------
if __name__ == "__main__":
    os.makedirs(FIG_DIR, exist_ok=True)

    rows  = load_runs(CSV)
    stats = stats_by_condition(rows)

    print_summary(stats)
    print_per_task(rows)

    print("\nGenerating figures...")
    plot_energy(stats, FIG_DIR)
    plot_steps(stats, FIG_DIR)
    plot_success_rate(stats, FIG_DIR)
    plot_per_task_steps(rows, FIG_DIR)

    print(f"\nDone. Figures saved to {FIG_DIR}/")

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
import json
import os
import re
from collections import defaultdict

import matplotlib.pyplot as plt
import numpy as np

CSV          = "results/runs.csv"
ACCURACY_CSV = "results/accuracy.csv"
TRAJ_DIR     = "results/trajectories"
FIG_DIR      = "results/figures"

# Bash patterns that indicate a real file edit
_EDIT_PATTERNS = [
    r"sed -i", r"echo .+>>? ", r"cat > ", r"cat >>",
    r"tee ", r"printf .+>", r"> .+\.py", r">> .+\.py",
]

# Conditions shown in the report (in display order)
COND_ORDER  = ["baseline", "exception_debug_skill", "logic_debug_skill", "feature_skill"]
COND_LABELS = {
    "baseline":              "Baseline",
    "exception_debug_skill": "Exception Debug Skill",
    "logic_debug_skill":     "Logic Debug Skill",
    "feature_skill":         "Feature Skill",
}
COLORS = {
    "baseline":              "#6c757d",
    "exception_debug_skill": "#0d6efd",
    "logic_debug_skill":     "#198754",
    "feature_skill":         "#fd7e14",
}

# All 30 batch tasks and their types
TASK_TYPE = {
    # --- exception_debug: bugs with a clear exception / traceback ---
    "astropy__astropy-14995":           "exception_debug",
    "mwaskom__seaborn-3190":            "exception_debug",
    "mwaskom__seaborn-3010":            "exception_debug",
    "matplotlib__matplotlib-22711":     "exception_debug",
    "matplotlib__matplotlib-22835":     "exception_debug",
    "psf__requests-2148":               "exception_debug",
    "psf__requests-2674":               "exception_debug",
    # --- logic_debug: wrong result / silent bugs, no exception ---
    "django__django-11001":             "logic_debug",
    "astropy__astropy-6938":            "logic_debug",
    "django__django-11019":             "logic_debug",
    "django__django-11039":             "logic_debug",
    "astropy__astropy-12907":           "logic_debug",
    "matplotlib__matplotlib-23299":     "logic_debug",
    "matplotlib__matplotlib-23314":     "logic_debug",
    "psf__requests-1963":               "logic_debug",
    "psf__requests-2317":               "logic_debug",
    "psf__requests-3362":               "logic_debug",
    "mwaskom__seaborn-2848":            "logic_debug",
    "mwaskom__seaborn-3407":            "logic_debug",
    "pydata__xarray-4094":              "logic_debug",
    # --- feature ---
    "pallets__flask-4992":              "feature",
    "astropy__astropy-14365":           "feature",
    "django__django-10924":             "feature",
    "django__django-10914":             "feature",
    "astropy__astropy-14182":           "feature",
    "matplotlib__matplotlib-18869":     "feature",
    "pallets__flask-4045":              "feature",
    "pallets__flask-5063":              "feature",
    "pydata__xarray-3364":              "feature",
    "pydata__xarray-4248":              "feature",
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
        r["code_changed"] = r.get("code_changed", "") == "True"
        r["resolved"]     = False  # filled in by merge_accuracy()
    return rows


def load_accuracy(csv_path: str) -> dict:
    """Returns dict keyed by (task_id, condition, run) → resolved (bool)."""
    resolved = {}
    if not os.path.exists(csv_path):
        return resolved
    with open(csv_path, newline="") as f:
        for row in csv.DictReader(f):
            key = (row["task_id"], row["condition"], row["run"])
            resolved[key] = row["resolved"].strip().lower() == "true"
    return resolved


def merge_accuracy(rows: list[dict], accuracy: dict) -> list[dict]:
    """Attach resolved field from accuracy.csv to each run row."""
    for r in rows:
        key = (r["task_id"], r["condition"], r["run"])
        r["resolved"] = accuracy.get(key, False)
    return rows


def valid(rows: list[dict]) -> list[dict]:
    """Keep all runs where energy was measured, regardless of resolved status.
    Energy is averaged over all runs to reflect true cost including failures.
    """
    return [r for r in rows if r["energy_kwh"] > 0]


# ------------------------------------------------------------------
# Aggregation
# ------------------------------------------------------------------
def avg(vals: list) -> float:
    return sum(vals) / len(vals) if vals else 0.0


def stats_by_condition(rows: list[dict]) -> dict:
    """
    Returns dict: condition -> stats including energy_all and energy_resolved.
    energy_all: avg over all runs with measured energy (resolved and unresolved).
    energy_resolved: avg over harness-resolved runs only.
    """
    by_cond = defaultdict(list)
    all_by_cond = defaultdict(list)
    for r in rows:
        all_by_cond[r["condition"]].append(r)
        if r["energy_kwh"] > 0:
            by_cond[r["condition"]].append(r)

    result = {}
    for cond in all_by_cond:
        all_r         = all_by_cond[cond]
        measured      = by_cond[cond]
        resolved_rows = [r for r in measured if r["resolved"]]
        has_resolved  = any(r["resolved"] for r in all_r)
        result[cond] = {
            "energy":          avg([r["energy_kwh"] for r in measured]),
            "energy_all":      avg([r["energy_kwh"] for r in measured]),
            "energy_resolved": avg([r["energy_kwh"] for r in resolved_rows]) if resolved_rows else None,
            "steps":           avg([r["steps"]       for r in measured]),
            "duration":        avg([r["duration_s"]  for r in measured]),
            "resolved_rate":   sum(r["resolved"]  for r in all_r) / len(all_r) if has_resolved else None,
            "success_rate":    sum(r["submitted"] for r in all_r) / len(all_r),
            "n_total":         len(all_r),
            "n_valid":         len(measured),
            "n_resolved":      len(resolved_rows),
        }
    return result


def stats_by_task(rows: list[dict], condition: str) -> dict:
    """energy and steps per task for a given condition."""
    result = {}
    for task_id in TASK_TYPE:
        task_rows = [r for r in rows
                     if r["task_id"] == task_id
                     and r["condition"] == condition
                     and r["energy_kwh"] > 0]
        res_rows = [r for r in task_rows if r["resolved"]]
        result[task_id] = {
            "energy":          avg([r["energy_kwh"] for r in task_rows]),
            "energy_resolved": avg([r["energy_kwh"] for r in res_rows]) if res_rows else None,
            "steps":           avg([r["steps"] for r in task_rows]),
            "n":               len(task_rows),
            "n_resolved":      len(res_rows),
        }
    return result


# ------------------------------------------------------------------
# Console report
# ------------------------------------------------------------------
def print_summary(stats: dict, baseline_key: str = "baseline"):
    b_energy_all      = stats.get(baseline_key, {}).get("energy_all",      0)
    b_energy_resolved = stats.get(baseline_key, {}).get("energy_resolved",  0) or 0

    has_resolved = any(s.get("resolved_rate") is not None for s in stats.values())

    print("\n" + "=" * 100)
    print("CONDITION SUMMARY")
    print("=" * 100)
    print(
        f"{'Condition':<22} {'n':>4} {'Enrg-All(kWh)':>15} {'vs base':>9} "
        f"{'Enrg-Resolved(kWh)':>20} {'vs base':>9} "
        f"{'Steps':>7} {'Resolved' if has_resolved else 'Submit':>9}"
    )
    print("-" * 100)

    for cond in COND_ORDER:
        if cond not in stats:
            continue
        s = stats[cond]

        delta_all = ((s["energy_all"] - b_energy_all) / b_energy_all * 100) if b_energy_all > 0 else 0
        dir_all   = "LESS" if delta_all < 0 else "more"
        str_all   = f"{abs(delta_all):.1f}% {dir_all}" if b_energy_all > 0 and cond != baseline_key else "—"

        if s["energy_resolved"] is not None and b_energy_resolved > 0:
            delta_res = ((s["energy_resolved"] - b_energy_resolved) / b_energy_resolved * 100)
            dir_res   = "LESS" if delta_res < 0 else "more"
            str_res   = f"{abs(delta_res):.1f}% {dir_res}" if cond != baseline_key else "—"
            e_res_str = f"{s['energy_resolved']:.8f}"
        else:
            str_res   = "—"
            e_res_str = "     n/a     "

        rate = s["resolved_rate"] if has_resolved and s["resolved_rate"] is not None else s["success_rate"]
        print(
            f"{COND_LABELS[cond]:<22} {s['n_valid']:>4} "
            f"{s['energy_all']:>15.8f} {str_all:>9} "
            f"{e_res_str:>20} {str_res:>9} "
            f"{s['steps']:>7.1f} {rate:>8.0%}"
        )

    print("  * Energy-All: avg over all runs with measured energy (including failed)")
    print("  * Energy-Resolved: avg over harness-resolved runs only")
    print("=" * 100)


def print_per_task(rows: list[dict]):
    b_stats  = stats_by_task(rows, "baseline")
    ex_stats = stats_by_task(rows, "exception_debug_skill")
    lo_stats = stats_by_task(rows, "logic_debug_skill")
    fs_stats = stats_by_task(rows, "feature_skill")

    def skill_stats(task_id, ttype):
        if ttype == "exception_debug": return ex_stats[task_id]
        if ttype == "logic_debug":     return lo_stats[task_id]
        return fs_stats[task_id]

    print("\n" + "=" * 80)
    print("PER-TASK: baseline vs task_specific_skill  (valid runs only)")
    print("=" * 80)
    print(f"{'Task':<38} {'type':<14} {'B steps':>8} {'S steps':>8} {'B energy':>12} {'S energy':>12}")
    print("-" * 80)
    for task_id, ttype in TASK_TYPE.items():
        short  = task_id.split("__")[1][:35]
        b      = b_stats[task_id]
        s      = skill_stats(task_id, ttype)
        b_e    = f"{b['energy']:.6f}" if b["n"] else "    n/a "
        s_e    = f"{s['energy']:.6f}" if s["n"] else "    n/a "
        b_s    = f"{b['steps']:.1f}"  if b["n"] else " n/a"
        s_s    = f"{s['steps']:.1f}"  if s["n"] else " n/a"
        print(f"{short:<38} {ttype:<14} {b_s:>8} {s_s:>8} {b_e:>12} {s_e:>12}")
    print("=" * 80)


# ------------------------------------------------------------------
# Figures
# ------------------------------------------------------------------
def plot_energy(stats: dict, out_dir: str):
    conds  = [c for c in COND_ORDER if c in stats and stats[c]["n_valid"] > 0]
    labels = [COND_LABELS[c] for c in conds]
    colors = [COLORS[c] for c in conds]

    vals_all      = [stats[c]["energy_all"] * 1000 for c in conds]
    vals_resolved = [
        (stats[c]["energy_resolved"] * 1000 if stats[c]["energy_resolved"] is not None else 0)
        for c in conds
    ]
    has_resolved = any(stats[c]["energy_resolved"] is not None for c in conds)

    x     = np.arange(len(conds))
    width = 0.35

    fig, ax = plt.subplots(figsize=(10, 5))

    bars_all = ax.bar(x - width / 2, vals_all, width,
                      color=colors, alpha=0.6, edgecolor="white", label="All runs")

    if has_resolved:
        bars_res = ax.bar(x + width / 2, vals_resolved, width,
                          color=colors, alpha=1.0, edgecolor="white", label="Resolved runs only",
                          hatch="//")
        for bar, val in zip(bars_res, vals_resolved):
            if val > 0:
                ax.text(bar.get_x() + bar.get_width() / 2,
                        bar.get_height() + max(vals_all) * 0.01,
                        f"{val:.4f}", ha="center", va="bottom", fontsize=8)

    for bar, val in zip(bars_all, vals_all):
        ax.text(bar.get_x() + bar.get_width() / 2,
                bar.get_height() + max(vals_all) * 0.01,
                f"{val:.4f}", ha="center", va="bottom", fontsize=8)

    ax.set_xticks(x)
    ax.set_xticklabels(labels)
    ax.set_ylabel("Average Energy (milli-kWh)")
    ax.set_title("Energy Consumption per Condition\n(all runs vs. resolved runs only)")
    ax.set_ylim(0, max(vals_all) * 1.25)
    ax.legend()
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
    colors = [COLORS[c] for c in conds]

    has_resolved = any(
        s.get("resolved_rate") is not None for s in stats.values()
    )

    fig, ax = plt.subplots(figsize=(8, 5))

    if has_resolved:
        values = [(stats[c]["resolved_rate"] or 0) * 100 for c in conds]
        bars = ax.bar(labels, values, color=colors, width=0.5, edgecolor="white")
        for bar, val in zip(bars, values):
            ax.text(bar.get_x() + bar.get_width() / 2,
                    bar.get_height() + 1,
                    f"{val:.0f}%", ha="center", va="bottom", fontsize=9)
        ax.set_ylabel("Resolved Rate (%)")
        ax.set_title("Harness-Resolved Rate per Condition\n(FAIL_TO_PASS tests passed)")
        ax.set_ylim(0, 110)
    else:
        ax.set_title("Harness-Resolved Rate per Condition")
        ax.set_ylabel("Resolved Rate (%)")
        ax.set_ylim(0, 110)

    ax.spines[["top", "right"]].set_visible(False)
    plt.tight_layout()
    path = os.path.join(out_dir, "success_by_condition.png")
    plt.savefig(path, dpi=150)
    plt.close()
    print(f"  Saved: {path}")


def plot_per_task_steps(rows: list[dict], out_dir: str):
    b_stats  = stats_by_task(rows, "baseline")
    ex_stats = stats_by_task(rows, "exception_debug_skill")
    lo_stats = stats_by_task(rows, "logic_debug_skill")
    fs_stats = stats_by_task(rows, "feature_skill")

    def specific(task_id):
        ttype = TASK_TYPE[task_id]
        if ttype == "exception_debug": return ex_stats[task_id]
        if ttype == "logic_debug":     return lo_stats[task_id]
        return fs_stats[task_id]

    tasks_with_data = [t for t in TASK_TYPE
                       if b_stats[t]["n"] > 0 and specific(t)["n"] > 0]
    if not tasks_with_data:
        return

    short_names = [t.split("__")[1][:20] for t in tasks_with_data]
    x     = np.arange(len(tasks_with_data))
    width = 0.35

    b_vals = [b_stats[t]["steps"]    for t in tasks_with_data]
    s_vals = [specific(t)["steps"]   for t in tasks_with_data]
    s_colors = [
        COLORS["exception_debug_skill"] if TASK_TYPE[t] == "exception_debug"
        else COLORS["logic_debug_skill"] if TASK_TYPE[t] == "logic_debug"
        else COLORS["feature_skill"]
        for t in tasks_with_data
    ]

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
# Real code-change analysis (trajectory-level)
# ------------------------------------------------------------------
def load_code_changes(traj_dir: str) -> list[dict]:
    """
    Scans every trajectory JSON for bash commands that write to a file.
    Returns one dict per run: task_id, condition, run, changed (bool), submitted (bool).
    Only considers current-experiment runs (run1/2/3, known conditions).
    """
    results = []
    for fname in sorted(os.listdir(traj_dir)):
        if not fname.endswith(".json"):
            continue
        parts = fname.replace(".json", "").rsplit("__", 2)
        if len(parts) != 3:
            continue
        task_id, condition, run_str = parts
        run = run_str.replace("run", "")
        if run not in ("1", "2", "3"):
            continue
        if condition not in ("baseline", "debug_skill", "feature_skill"):
            continue

        with open(os.path.join(traj_dir, fname)) as f:
            data = json.load(f)

        info = data.get("info", {})
        submitted = info.get("exit_status", "") == "Submitted"

        changed = False
        for msg in data.get("messages", []):
            for tc in msg.get("tool_calls", []):
                args_str = tc.get("function", {}).get("arguments", "")
                try:
                    cmd = json.loads(args_str).get("command", "")
                except Exception:
                    cmd = args_str
                if any(re.search(p, cmd) for p in _EDIT_PATTERNS):
                    changed = True
                    break

        results.append({
            "task_id":   task_id,
            "condition": condition,
            "run":       run,
            "changed":   changed,
            "submitted": submitted,
        })
    return results


def print_code_change_summary(change_rows: list[dict]):
    print("\n" + "=" * 72)
    print("REAL CODE CHANGES  (bash file-edit commands found in trajectory)")
    print("=" * 72)
    print(f"{'Condition':<16} {'Runs':>5} {'Changed':>8} {'Change%':>8} "
          f"{'Submitted':>10} {'Changed+Sub':>12}")
    print("-" * 72)

    for cond in COND_ORDER:
        rows = [r for r in change_rows if r["condition"] == cond]
        if not rows:
            continue
        changed     = [r for r in rows if r["changed"]]
        submitted   = [r for r in rows if r["submitted"]]
        chg_sub     = [r for r in rows if r["changed"] and r["submitted"]]
        pct = len(changed) / len(rows) * 100
        print(f"{COND_LABELS[cond]:<16} {len(rows):>5} {len(changed):>8} "
              f"{pct:>7.0f}% {len(submitted):>10} {len(chg_sub):>12}")

    all_sub  = [r for r in change_rows if r["submitted"]]
    real_sub = [r for r in change_rows if r["submitted"] and r["changed"]]
    print("-" * 72)
    print(f"{'TOTAL':<16} {len(change_rows):>5} "
          f"{sum(r['changed'] for r in change_rows):>8}")
    print(f"\nOf {len(all_sub)} Submitted runs: "
          f"{len(real_sub)} ({len(real_sub)/len(all_sub)*100:.0f}%) "
          f"had real code changes — "
          f"{len(all_sub)-len(real_sub)} submitted without editing anything.")
    print("=" * 72)


def plot_code_change_rate(change_rows: list[dict], out_dir: str):
    conds  = [c for c in COND_ORDER if any(r["condition"] == c for r in change_rows)]
    labels = [COND_LABELS[c] for c in conds]
    colors = [COLORS[c] for c in conds]

    change_rates = []
    for cond in conds:
        rows = [r for r in change_rows if r["condition"] == cond]
        change_rates.append(len([r for r in rows if r["changed"]]) / len(rows) * 100 if rows else 0)

    fig, ax = plt.subplots(figsize=(8, 5))
    bars = ax.bar(labels, change_rates, color=colors, width=0.5, edgecolor="white")
    for bar, val in zip(bars, change_rates):
        ax.text(bar.get_x() + bar.get_width() / 2,
                bar.get_height() + 1,
                f"{val:.0f}%", ha="center", va="bottom", fontsize=9)

    ax.set_ylabel("Runs with Real File Edit (%)")
    ax.set_title("Rate of Real Code Changes per Condition\n"
                 "(bash file-write commands found in trajectory)")
    ax.set_ylim(0, 50)
    ax.spines[["top", "right"]].set_visible(False)
    plt.tight_layout()
    path = os.path.join(out_dir, "code_change_rate.png")
    plt.savefig(path, dpi=150)
    plt.close()
    print(f"  Saved: {path}")


# ------------------------------------------------------------------
# Main
# ------------------------------------------------------------------
if __name__ == "__main__":
    os.makedirs(FIG_DIR, exist_ok=True)

    rows     = load_runs(CSV)
    accuracy = load_accuracy(ACCURACY_CSV)
    rows     = merge_accuracy(rows, accuracy)

    if accuracy:
        print(f"Loaded accuracy.csv: {len(accuracy)} evaluated patches")
    else:
        print("No accuracy.csv found — resolved metric not available yet")

    stats = stats_by_condition(rows)

    print_summary(stats)
    print_per_task(rows)

    change_rows = load_code_changes(TRAJ_DIR)
    print_code_change_summary(change_rows)

    print("\nGenerating figures...")
    plot_energy(stats, FIG_DIR)
    plot_steps(stats, FIG_DIR)
    plot_success_rate(stats, FIG_DIR)
    plot_per_task_steps(rows, FIG_DIR)
    plot_code_change_rate(change_rows, FIG_DIR)

    print(f"\nDone. Figures saved to {FIG_DIR}/")

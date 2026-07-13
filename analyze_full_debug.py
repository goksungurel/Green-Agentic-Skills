"""
analyze_full_debug.py
----------------------
Same as analyze.py, but for the separate full-systematic-debug-skill pilot
(results/runs_full_debug.csv + results/accuracy_full_debug.csv).

Does not touch results/runs.csv, results/accuracy.csv, results/figures/, or
analyze.py's own output — fully additive, separate pilot.

Usage:
    python3 analyze_full_debug.py
"""

import csv
import json
import os
from collections import defaultdict

import matplotlib.pyplot as plt
import numpy as np

CSV          = "results/runs_full_debug.csv"
ACCURACY_CSV = "results/accuracy_full_debug.csv"
TRAJ_DIR     = "results/trajectories_full_debug"
FIG_DIR      = "results/figures_full_debug"

COND_ORDER  = ["baseline", "full_systematic_debug"]
COND_LABELS = {
    "baseline":              "Baseline",
    "full_systematic_debug": "Full Systematic-Debug Skill",
}
COLORS = {
    "baseline":              "#6c757d",
    "full_systematic_debug": "#6f42c1",
}

# Same 30 batch tasks as the main experiment (task type doesn't matter here —
# this pilot applies ONE unmodified skill uniformly to all 30, not per-category).
ALL_TASKS = [
    "astropy__astropy-14995", "mwaskom__seaborn-3190", "mwaskom__seaborn-3010",
    "matplotlib__matplotlib-22711", "matplotlib__matplotlib-22835",
    "psf__requests-2148", "psf__requests-2674", "django__django-11001",
    "astropy__astropy-6938", "django__django-11019", "django__django-11039",
    "astropy__astropy-12907", "matplotlib__matplotlib-23299",
    "matplotlib__matplotlib-23314", "psf__requests-1963", "psf__requests-2317",
    "psf__requests-3362", "mwaskom__seaborn-2848", "mwaskom__seaborn-3407",
    "pydata__xarray-4094", "pallets__flask-4992", "astropy__astropy-14365",
    "django__django-10924", "django__django-10914", "astropy__astropy-14182",
    "matplotlib__matplotlib-18869", "pallets__flask-4045", "pallets__flask-5063",
    "pydata__xarray-3364", "pydata__xarray-4248",
]


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
        r["evaluated"]    = False  # was this run actually scored by the harness?
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
    for r in rows:
        key = (r["task_id"], r["condition"], r["run"])
        r["evaluated"] = key in accuracy
        r["resolved"]  = accuracy.get(key, False)
    return rows


# ------------------------------------------------------------------
# Aggregation
# ------------------------------------------------------------------
def avg(vals: list) -> float:
    return sum(vals) / len(vals) if vals else 0.0


def stats_by_condition(rows: list[dict]) -> dict:
    by_cond = defaultdict(list)
    all_by_cond = defaultdict(list)
    for r in rows:
        all_by_cond[r["condition"]].append(r)
        if r["energy_kwh"] > 0:
            by_cond[r["condition"]].append(r)

    result = {}
    for cond in all_by_cond:
        all_r          = all_by_cond[cond]
        measured       = by_cond[cond]
        resolved_rows  = [r for r in measured if r["resolved"]]
        evaluated_rows = [r for r in all_r if r["evaluated"]]
        result[cond] = {
            "energy_all":      avg([r["energy_kwh"] for r in measured]),
            "energy_resolved": avg([r["energy_kwh"] for r in resolved_rows]) if resolved_rows else None,
            "steps":           avg([r["steps"]       for r in measured]),
            "duration":        avg([r["duration_s"]  for r in measured]),
            "resolved_rate":   (len(resolved_rows) / len(evaluated_rows)) if evaluated_rows else None,
            "success_rate":    sum(r["submitted"] for r in all_r) / len(all_r),
            "n_total":         len(all_r),
            "n_valid":         len(measured),
            "n_resolved":      len(resolved_rows),
            "n_evaluated":     len(evaluated_rows),
        }
    return result


def stats_by_task(rows: list[dict], condition: str) -> dict:
    result = {}
    for task_id in ALL_TASKS:
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
    print("CONDITION SUMMARY — full_systematic_debug pilot")
    print("=" * 100)
    print(
        f"{'Condition':<28} {'n':>4} {'Enrg-All(kWh)':>15} {'vs base':>9} "
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

        if has_resolved:
            rate_str = f"{s['resolved_rate']:>8.0%}" if s["resolved_rate"] is not None else "     n/a"
        else:
            rate_str = f"{s['success_rate']:>8.0%}"
        print(
            f"{COND_LABELS[cond]:<28} {s['n_valid']:>4} "
            f"{s['energy_all']:>15.8f} {str_all:>9} "
            f"{e_res_str:>20} {str_res:>9} "
            f"{s['steps']:>7.1f} {rate_str}"
        )
        print(f"{'':<28} (resolved: {s['n_resolved']}/{s['n_evaluated']} evaluated, "
              f"{s['n_evaluated']}/{s['n_total']} runs evaluated)")

    print("  * Energy-All: avg over all runs with measured energy (including failed)")
    print("  * Energy-Resolved: avg over harness-resolved runs only")
    print("=" * 100)


def print_per_task(rows: list[dict]):
    b_stats = stats_by_task(rows, "baseline")
    f_stats = stats_by_task(rows, "full_systematic_debug")

    print("\n" + "=" * 90)
    print("PER-TASK: baseline vs full_systematic_debug")
    print("=" * 90)
    print(f"{'Task':<38} {'B steps':>8} {'F steps':>8} {'B energy':>12} {'F energy':>12} {'B res':>6} {'F res':>6}")
    print("-" * 90)
    for task_id in ALL_TASKS:
        short = task_id.split("__")[1][:35]
        b = b_stats[task_id]
        f = f_stats[task_id]
        b_e = f"{b['energy']:.6f}" if b["n"] else "    n/a "
        f_e = f"{f['energy']:.6f}" if f["n"] else "    n/a "
        b_s = f"{b['steps']:.1f}"  if b["n"] else " n/a"
        f_s = f"{f['steps']:.1f}"  if f["n"] else " n/a"
        print(f"{short:<38} {b_s:>8} {f_s:>8} {b_e:>12} {f_e:>12} {b['n_resolved']:>6} {f['n_resolved']:>6}")
    print("=" * 90)


# ------------------------------------------------------------------
# Real code-change analysis (trajectory-level)
# ------------------------------------------------------------------
def load_code_changes(traj_dir: str, csv_rows: list[dict]) -> list[dict]:
    valid_lookup = {}
    changed_lookup = {}
    for r in csv_rows:
        key = (r["task_id"], r["condition"], r["run"])
        vs = r.get("valid_syntax", "n/a")
        valid_lookup[key] = None if vs == "n/a" else (vs == "True")
        cc = r.get("code_changed")
        if isinstance(cc, bool):
            changed_lookup[key] = cc
        elif cc in ("True", "False"):
            changed_lookup[key] = (cc == "True")

    results = []
    if not os.path.isdir(traj_dir):
        return results
    for fname in sorted(os.listdir(traj_dir)):
        if not fname.endswith(".json"):
            continue
        parts = fname.replace(".json", "").rsplit("__", 2)
        if len(parts) != 3:
            continue
        task_id, condition, run_str = parts
        run = run_str.replace("run", "")
        if not run.isdigit():
            continue
        if condition not in COND_ORDER:
            continue

        with open(os.path.join(traj_dir, fname)) as f:
            data = json.load(f)

        info = data.get("info", {})
        submitted = info.get("exit_status", "") == "Submitted"

        key = (task_id, condition, run)
        if key not in changed_lookup:
            continue

        changed = changed_lookup[key]

        results.append({
            "task_id":   task_id,
            "condition": condition,
            "run":       run,
            "changed":   changed,
            "submitted": submitted,
            "valid":     valid_lookup.get(key),
        })
    return results


def print_code_change_summary(change_rows: list[dict]):
    print("\n" + "=" * 88)
    print("REAL CODE CHANGES  (from runs_full_debug.csv's code_changed / valid_syntax)")
    print("=" * 88)
    print(f"{'Condition':<28} {'Runs':>5} {'Changed':>8} {'Change%':>8} "
          f"{'Valid':>6} {'Valid%':>7} {'Submitted':>10} {'Changed+Sub':>12}")
    print("-" * 88)

    for cond in COND_ORDER:
        rows = [r for r in change_rows if r["condition"] == cond]
        if not rows:
            continue
        changed     = [r for r in rows if r["changed"]]
        valid_chg   = [r for r in rows if r["changed"] and r["valid"] is True]
        submitted   = [r for r in rows if r["submitted"]]
        chg_sub     = [r for r in rows if r["changed"] and r["submitted"]]
        pct = len(changed) / len(rows) * 100
        valid_pct = (len(valid_chg) / len(changed) * 100) if changed else 0
        print(f"{COND_LABELS[cond]:<28} {len(rows):>5} {len(changed):>8} "
              f"{pct:>7.0f}% {len(valid_chg):>6} {valid_pct:>6.0f}% "
              f"{len(submitted):>10} {len(chg_sub):>12}")

    if change_rows:
        all_sub    = [r for r in change_rows if r["submitted"]]
        real_sub   = [r for r in change_rows if r["submitted"] and r["changed"]]
        real_valid = [r for r in change_rows if r["submitted"] and r["changed"] and r["valid"] is True]
        print("-" * 88)
        if all_sub:
            print(f"\nOf {len(all_sub)} Submitted runs: "
                  f"{len(real_sub)} ({len(real_sub)/len(all_sub)*100:.0f}%) had real code changes, "
                  f"but only {len(real_valid)} ({len(real_valid)/len(all_sub)*100:.0f}%) of those "
                  f"changes were syntactically valid Python.")
    print("=" * 88)


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

    fig, ax = plt.subplots(figsize=(8, 5))
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
    ax.set_title("Energy Consumption per Condition — full_systematic_debug pilot\n(all runs vs. resolved runs only)")
    ax.set_ylim(0, max(vals_all) * 1.25 if max(vals_all) else 1)
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

    fig, ax = plt.subplots(figsize=(6, 5))
    bars = ax.bar(labels, values, color=colors, width=0.5, edgecolor="white")

    for bar, val in zip(bars, values):
        ax.text(bar.get_x() + bar.get_width() / 2,
                bar.get_height() + max(values) * 0.01,
                f"{val:.1f}", ha="center", va="bottom", fontsize=9)

    ax.set_ylabel("Average LLM Calls (steps)")
    ax.set_title("Agent Steps per Condition — full_systematic_debug pilot\n(all measured runs, incl. failures)")
    ax.set_ylim(0, max(values) * 1.2 if max(values) else 1)
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

    has_resolved = any(s.get("resolved_rate") is not None for s in stats.values())

    fig, ax = plt.subplots(figsize=(6, 5))

    if has_resolved:
        values = [(stats[c]["resolved_rate"] or 0) * 100 for c in conds]
        bars = ax.bar(labels, values, color=colors, width=0.5, edgecolor="white")
        for bar, val in zip(bars, values):
            ax.text(bar.get_x() + bar.get_width() / 2,
                    bar.get_height() + 1,
                    f"{val:.1f}%", ha="center", va="bottom", fontsize=9)
        ax.set_ylabel("Resolved Rate (%)")
        ax.set_title("Harness-Resolved Rate per Condition — full_systematic_debug pilot\n(FAIL_TO_PASS tests passed, of evaluated runs)")
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


def plot_code_change_rate(change_rows: list[dict], out_dir: str):
    conds  = [c for c in COND_ORDER if any(r["condition"] == c for r in change_rows)]
    if not conds:
        return
    labels = [COND_LABELS[c] for c in conds]
    colors = [COLORS[c] for c in conds]

    change_rates = []
    valid_rates = []
    for cond in conds:
        rows = [r for r in change_rows if r["condition"] == cond]
        changed = [r for r in rows if r["changed"]]
        change_rates.append(len(changed) / len(rows) * 100 if rows else 0)
        valid_rates.append(
            len([r for r in changed if r["valid"] is True]) / len(rows) * 100 if rows else 0
        )

    x = np.arange(len(conds))
    width = 0.35
    fig, ax = plt.subplots(figsize=(6, 5))
    ax.bar(x - width/2, change_rates, width, label="Changed", color=colors, alpha=0.6, edgecolor="white")
    ax.bar(x + width/2, valid_rates, width, label="Changed + Valid", color=colors, alpha=1.0, edgecolor="white", hatch="//")
    for i, val in enumerate(change_rates):
        ax.text(x[i] - width/2, val + 1, f"{val:.0f}%", ha="center", va="bottom", fontsize=9)
    for i, val in enumerate(valid_rates):
        ax.text(x[i] + width/2, val + 1, f"{val:.0f}%", ha="center", va="bottom", fontsize=9)

    ax.set_xticks(x)
    ax.set_xticklabels(labels)
    ax.set_ylabel("Runs (%)")
    ax.set_title("Real Code-Change Rate per Condition — full_systematic_debug pilot")
    ax.set_ylim(0, 50)
    ax.legend()
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
        print(f"Loaded {ACCURACY_CSV}: {len(accuracy)} evaluated patches")
    else:
        print(f"No {ACCURACY_CSV} found — resolved metric not available yet")

    stats = stats_by_condition(rows)

    print_summary(stats)
    print_per_task(rows)

    change_rows = load_code_changes(TRAJ_DIR, csv_rows=rows)
    print_code_change_summary(change_rows)

    print("\nGenerating figures...")
    plot_energy(stats, FIG_DIR)
    plot_steps(stats, FIG_DIR)
    plot_success_rate(stats, FIG_DIR)
    plot_code_change_rate(change_rows, FIG_DIR)

    print(f"\nDone. Figures saved to {FIG_DIR}/")

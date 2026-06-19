"""
Selects 30 diverse tasks from SWE-bench Lite and saves them to selected_tasks.csv.

Why this file exists:
    Running all 300 tasks would take too long.
    We select 30 tasks from 7 different repositories for diversity.
    Diversity matters: different repos = different code styles = more reliable results.
"""

from datasets import load_dataset
import pandas as pd

# -----------------------------------------------------------------
# 1. Load SWE-bench Lite dataset from Hugging Face
# -----------------------------------------------------------------
print("Loading SWE-bench Lite...")
ds = load_dataset("princeton-nlp/SWE-bench_Lite", split="test")
df = pd.DataFrame(ds)
print(f"Total tasks available: {len(df)}")
print(f"Columns: {list(df.columns)}\n")

# -----------------------------------------------------------------
# 2. Define how many tasks to select from each repository
# -----------------------------------------------------------------
# Total: 30 tasks from 7 repositories
# These repos were chosen because:
#   - They have enough tasks in SWE-bench Lite
#   - They are all Python projects (compatible with our skill.md)
#   - They cover different domains (web, science, visualization, data)

selection = {
    "django/django":                5,  # web framework
    "astropy/astropy":              5,  # scientific computing
    "matplotlib/matplotlib":        5,  # data visualization
    "psf/requests":                 5,  # HTTP library
    "mwaskom/seaborn":              4,  # statistical visualization
    "pallets/flask":                3,  # lightweight web framework
    "pydata/xarray":                3,  # multi-dimensional data
}

print("Selection plan:")
for repo, count in selection.items():
    available = len(df[df['repo'] == repo])
    print(f"  {repo:<35} → select {count} (available: {available})")

# -----------------------------------------------------------------
# 3. Select tasks from each repository
# -----------------------------------------------------------------
selected = []

for repo, count in selection.items():
    repo_df = df[df['repo'] == repo]

    if len(repo_df) < count:
        # If not enough tasks in this repo, take all of them
        print(f"\n[WARNING] {repo} has only {len(repo_df)} tasks, taking all.")
        selected.append(repo_df)
    else:
        # Take the first N tasks (deterministic, reproducible)
        selected.append(repo_df.head(count))

# Combine all selected tasks into one DataFrame
result = pd.concat(selected, ignore_index=True)

# -----------------------------------------------------------------
# 4. Keep only the columns we need for the experiment
# -----------------------------------------------------------------
result = result[['instance_id', 'repo', 'base_commit', 'problem_statement']]

# -----------------------------------------------------------------
# 5. Save to CSV
# -----------------------------------------------------------------
result.to_csv("selected_tasks.csv", index=False)

print(f"\n✅ {len(result)} tasks selected and saved to selected_tasks.csv")
print("\nRepository distribution:")
print(result['repo'].value_counts().to_string())
print("\nFirst 5 tasks:")
print(result[['instance_id', 'repo']].head().to_string(index=False))
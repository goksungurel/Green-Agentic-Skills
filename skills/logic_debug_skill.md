# Logic / Silent Bug Patterns
> Source: systematic-debugging by @obra (skillhub.club · S9.2)

## Step 1 — Search Keywords
The issue description names the broken sub-case (e.g. "nested models", "3+ objects", "multiline").
Search for the function or class handling that sub-case directly.

- Issue names a function → `grep -rn "def function_name" . --include="*.py"`
- Issue names a class → `grep -rn "class ClassName" . --include="*.py"`
- Issue is vague → grep for the data type or module name mentioned in the issue
- NEVER repeat the same search — if empty result, try a different keyword

## Step 2 — What to Look For
- Find the **conditional branch** or **recursive call** that handles the broken sub-case
- Compare it against a working branch in the same function
- Check every variable name — right operation, wrong object is a common mistake

## Common Fixes
| Pattern | Root Cause | Fix |
|---|---|---|
| `obj.replace(a, b)` does nothing | return value discarded | `obj = obj.replace(a, b)` |
| Same for `.strip()`, `re.sub()`, `.upper()` | return value discarded | assign back to variable |
| Regex misses multiline | `re.match` on string with `\n` | add `re.MULTILINE` or strip newlines first |
| Wrong variable | right operation, wrong object | check each variable name in the expression |
| Shared object mutated | missing `.copy()` | add `.copy()` when passing to function |
| Flag exists but ignored | condition not checked | `grep` for the flag name, add the check |

## Step 3 — Fix Rule
For **simple functions** (< 30 lines): change the one wrong line only.
For **complex functions** (> 30 lines): read the full function first, then fix only the broken branch.
One or two lines maximum — do not restructure.

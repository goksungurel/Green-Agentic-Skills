# Feature Addition Patterns
> Source: systematic-debugging by @obra (skillhub.club · S9.2)

## Step 1 — Search Keywords
Search for the **existing similar feature** first, not the new one.
Find how the codebase already does the closest thing to what the issue asks for.

## Step 2 — What to Look For
- Find a **similar existing method or parameter** in the same class/file
- Read how it is **called by other code** before touching the signature
- Copy the existing pattern exactly — do not invent a new style

## Common Patterns
| Feature Request | Where to Look | Fix Pattern |
|---|---|---|
| Add a parameter | existing method signature | `def method(self, ..., new_param=None)` + branch inside |
| Add file open mode | `open(path, "r")` call site | replace `"r"` with `mode` param defaulting to `"r"` |
| Add validation / raise | first use of the value | add `if bad_condition: raise ValueError(...)` guard |
| Case-insensitive match | the comparison expression | `.upper()` on both sides or `re.IGNORECASE` |
| Expose new attribute | near `__version__` or `__all__` | add attribute next to existing similar ones |
| Extend repr / output | `__repr__` or format function | add new field following adjacent field format |

## Step 3 — Fix Rule
- Use **backward-compatible defaults** — existing callers must not break
- If the issue shows exact code, implement it literally
- Do NOT add new imports unless strictly required
- Do NOT change public API signatures except to add an optional param

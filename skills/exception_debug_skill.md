# Exception Bug Patterns
> Source: systematic-debugging by @obra (skillhub.club · S9.2)

## Search Keywords
Extract the **function name** or **class name** from the traceback — then grep for that name in the local repo.
NEVER grep for the exception message text (e.g. `TypeError: ...`) — it will not appear in any source file.
NEVER use file paths from the traceback (e.g. `/Users/reporter/opt/anaconda3/.../widgets.py`) — those are the reporter's machine paths, they do NOT exist in the local repo. Take only the filename (e.g. `widgets.py`) and find it with grep:
`grep -rn "def REAL_FUNCTION_NAME" . --include="*.py" | head -20`
Search for the function that raises, not the caller:
- `TypeError: unsupported operand` → grep for the **function name** on the line that raises, e.g. `grep -rn "def REAL_FUNCTION_NAME"` — not the text `"TypeError"`
  (REAL_FUNCTION_NAME is NOT literal text — it is a placeholder. Replace it with
  the actual function name found on the traceback line that raises. Never type
  the literal words "REAL_FUNCTION_NAME" or "set_val" into a command.)
- `AttributeError: 'NoneType'` → grep for the **attribute name** being accessed
- `LinAlgError` → grep for the **numpy/scipy call** site by function name

## What to Look For
- Find a **similar working code path** in the same file — compare what it does differently
- Check whether the bad value comes from the **caller** (wrong type passed in) or from **within** the function (wrong transformation)

## Common Fixes
The "Exception" column below is a **category description**, NOT a grep pattern — never run these strings as grep commands.
| Exception | Root Cause | Fix |
|---|---|---|
| `TypeError: boolean subtract` | bool array used as numeric | `data.astype(float)` before operation |
| `TypeError: unsupported operand` | missing type coercion | add explicit cast at the operation site |
| `AttributeError: NoneType` | return value not checked | add `if result is None: ...` guard |
| `IndexError: out of bounds` | off-by-one in init | check array length at initialization |
| `LinAlgError / SVD` | NaN in data | `data.dropna()` before computation |
| `ValueError` from library | invalid input not validated | add guard before the library call |
| Exception not caught | missing except branch | add to existing `except (A, B)` tuple |

## Fix Rule
Fix at the **source of the bad value**, not at the exception site.
Make the smallest possible change — one line if possible.

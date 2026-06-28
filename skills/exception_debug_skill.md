# Exception Bug Patterns
> Source: systematic-debugging by @obra (skillhub.club · S9.2)

## Search Keywords
Extract the exception class and the failing function from the traceback.
Search for the function that raises, not the caller:
- `TypeError: unsupported operand` → search for the operation site, not the caller
- `AttributeError: 'NoneType'` → search for the attribute being accessed
- `LinAlgError` → search for the numpy/scipy call site

## What to Look For
- Find a **similar working code path** in the same file — compare what it does differently
- Check whether the bad value comes from the **caller** (wrong type passed in) or from **within** the function (wrong transformation)

## Common Fixes
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

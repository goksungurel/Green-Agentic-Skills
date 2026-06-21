# Python Coding Skill (General)

## Strategy
1. Read the issue carefully — decide if it's a **bug** (something crashes or returns wrong result) or a **feature** (something new to add)
2. Find the package location first: `python -c "import package_name; print(package_name.__file__)"`
3. Then search within that directory: `grep -rn "function_name" /path/from/step2/`
4. Make the smallest possible change that addresses the issue
5. Submit immediately

## If it's a bug
- Identify the exception type and the line it comes from
- Common fixes:
  - `TypeError` from `None`: add a None guard before the operation
  - `TypeError` from wrong type (e.g., bool): cast to the right type first
  - `IndexError`: remove or guard the out-of-bounds access
  - `ValueError` from non-invertible/unsupported op: wrap in `try/except`
  - `LinAlgError` / `SVD failed`: filter NaN/None before numeric computation
  - Logic bug (wrong result): find the exact variable/line responsible, fix only that

## If it's a feature
- Find a similar existing feature in the same file — copy its pattern
- Add the new param/method with a backward-compatible default
- Do NOT change existing behavior for existing callers

## Rules for both
- Fix or add ONLY what the issue describes — nothing else
- Do NOT refactor, clean up, or add tests
- One `grep`, one read, one edit, then submit

## Submission
```
echo COMPLETE_TASK_AND_SUBMIT_FINAL_OUTPUT
```

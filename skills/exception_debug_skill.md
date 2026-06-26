# Exception / Traceback Debug Skill

> Adapted from **systematic-debugging** by @obra (skillhub.club · S9.2 rated)
> for autonomous execution in mini-SWE-agent on SWE-bench tasks.

## The Iron Law

```
NO FIXES WITHOUT ROOT CAUSE INVESTIGATION FIRST
```

Random fixes waste steps and introduce new bugs.
ALWAYS find the root cause before changing any code.

## Phase 1 — Root Cause Investigation

1. **Read the exception from the issue carefully**
   - The exception type and message usually name the broken operation
   - Note the file path and line number if mentioned

2. **Find the file that raises the error — search by keyword:**
   ```
   grep -rn "error_keyword" . --include="*.py" | head -20
   ```
   - Search for class definitions: `grep -rn "class ClassName"` — NOT `ClassName.method`
   - Search for function definitions: `grep -rn "def method_name"` — NOT `obj.method_name`
   - If result is empty, try a DIFFERENT keyword — NEVER repeat the same search
   - NEVER use `find . -name` — NEVER use `python -c "import pkg; print(pkg.__file__)"`

3. **Read only the relevant section:**
   ```
   grep -n "keyword" /path/to/file.py
   sed -n '100,130p' /path/to/file.py
   ```

4. **Trace the root cause — where does the bad value originate?**
   - Which caller passes the wrong type or None?
   - Fix at the source — not at the symptom

## Phase 2 — Pattern Analysis

- Find a similar working code path in the same file
- Compare: what does the working path do that the broken one doesn't?
- Common exception root causes:
  - `TypeError: unsupported operand` → missing type check or coercion before the operation
  - `TypeError: boolean subtract` → cast boolean data to numeric: `data.astype(float)`
  - `IndexError: out of bounds` → off-by-one in array initialization
  - `ValueError` from library → invalid input not validated before passing in
  - `AttributeError: NoneType` → result not checked for None before use
  - `LinAlgError / SVD did not converge` → NaN/None in data, filter first: `data.dropna()`
  - Exception escaping unwrapped → catch alongside existing exceptions, re-raise as correct type

## Phase 3 — Hypothesis

- State clearly: "The root cause is X because Y"
- Make the SMALLEST possible change to test it
- ONE change at a time — do not bundle multiple fixes

## Phase 4 — Implement Fix

1. Apply the fix:
   - Simple one-line change: `sed -i '' 's/old/new/' /path/to/file.py`
   - Multi-line or special characters: use Python:
     ```
     python3 -c "c=open('/path/to/file.py').read(); open('/path/to/file.py','w').write(c.replace('old','new'))"
     ```
2. Verify: `grep -n "changed_keyword" /path/to/file.py`
3. Submit immediately — do not refactor, document, or add tests

## CRITICAL: Edit the actual file on disk

- Do NOT just run `python -c` to test in memory — that does not change the file
- Do NOT just print the fix — you must write it to the file
- For simple changes use `sed -i ''`; for multi-line/complex use Python as above

## Red Flags — Return to Phase 1

Stop and re-investigate if you find yourself:
- Repeating the same grep or command that already failed
- Guessing a fix without understanding where the error originates
- Changing multiple things at once
- Trying a third fix after two already failed

## Submission

When the fix is complete, run exactly:
```
echo COMPLETE_TASK_AND_SUBMIT_FINAL_OUTPUT
```

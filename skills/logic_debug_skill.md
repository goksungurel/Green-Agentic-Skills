# Logic / Silent Bug Debugging Skill

> Adapted from **systematic-debugging** by @obra (skillhub.club · S9.2 rated)
> for autonomous execution in mini-SWE-agent on SWE-bench tasks.

## The Iron Law

```
NO FIXES WITHOUT ROOT CAUSE INVESTIGATION FIRST
```

Random fixes waste steps and introduce new bugs.
ALWAYS find the root cause before changing any code.

## Phase 1 — Root Cause Investigation

1. **Read the issue description carefully**
   - Identify the function, class, or module the bug is in
   - The description usually names the broken sub-case (e.g. "nested models", "3+ objects", "multiline SQL")

2. **Find the relevant file — search by keyword:**
   ```
   grep -rn "unique_keyword" . --include="*.py" | head -20
   ```
   - Search for class definitions: `grep -rn "class ClassName"` — NOT `ClassName.method`
   - Search for function definitions: `grep -rn "def method_name"` — NOT `obj.method_name`
   - If result is empty, try a DIFFERENT keyword — NEVER repeat the same search
   - NEVER use `find . -name` — NEVER use `python -c "import pkg; print(pkg.__file__)"`

3. **Read only the relevant section:**
   ```
   grep -n "keyword_from_description" /path/to/file.py
   sed -n '100,130p' /path/to/file.py
   ```

4. **Trace the root cause**
   - Where does the wrong value originate?
   - What branch or condition handles the broken sub-case?
   - Fix at the source — not at the symptom

## Phase 2 — Pattern Analysis

- Find a similar working code path in the same file
- Compare: what does the working path do that the broken one doesn't?
- Common logic root causes:
  - **Return value not assigned**: `obj.replace(a, b)` → should be `obj = obj.replace(a, b)`
    (affects: `str.replace`, `bytes.replace`, `chararray.replace`, `re.sub`, `.strip`)
  - **Regex on multiline string**: strips newlines from sql before regex search
  - **Wrong variable used**: right operation, wrong object — check each variable name
  - **Missing `.copy()`**: mutation of shared object causes side effects elsewhere
  - **Wrong condition**: flag exists but not checked — `grep` for the flag name

## Phase 3 — Hypothesis

- State clearly: "The root cause is X because Y"
- Make the SMALLEST possible change to test it
- ONE change at a time — do not bundle multiple fixes

## Phase 4 — Implement Fix

**Simple function (< 30 lines):**
- Change the one wrong line — do not restructure the function

**Complex function (> 30 lines):**
- Read the full function before touching anything
- The issue description names the broken sub-case — find that conditional branch or recursive call
- Fix only that branch — one or two lines at most

Apply the fix:
- Simple one-line change: `sed -i '' 's/old/new/' /path/to/file.py`
- Multi-line or special characters: use Python:
  ```
  python3 -c "c=open('/path/to/file.py').read(); open('/path/to/file.py','w').write(c.replace('old','new'))"
  ```

Verify: `grep -n "changed_keyword" /path/to/file.py`

Submit immediately — do not refactor, document, or add tests.

## CRITICAL: Edit the actual file on disk

- Do NOT just run `python -c` to test in memory — that does not change the file
- Do NOT just print the fix — you must write it to the file
- For simple changes use `sed -i ''`; for multi-line/complex use Python as above

## Red Flags — Return to Phase 1

Stop and re-investigate if you find yourself:
- Repeating the same grep or command that already failed
- Guessing a fix without understanding where the value goes wrong
- Changing multiple things at once
- Trying a third fix after two already failed

## Submission

When the fix is complete, run exactly:
```
echo COMPLETE_TASK_AND_SUBMIT_FINAL_OUTPUT
```

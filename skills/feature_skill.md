# Python Feature Addition Skill

> Adapted from **systematic-debugging** by @obra (skillhub.club · S9.2 rated)
> for feature addition tasks in mini-SWE-agent on SWE-bench tasks.
> Core 4-phase structure from systematic-debugging; feature patterns custom-written.

## The Iron Law

```
UNDERSTAND THE EXISTING API BEFORE ADDING TO IT
```

Find a similar existing feature and copy its pattern exactly.
Never add a new feature without reading the surrounding code first.

## Phase 1 — Locate the Code to Extend

1. **Identify a unique keyword from the issue:** the class name, method name, or feature being extended.

2. **Find the file by keyword:**
   ```
   grep -rn "unique_keyword" . --include="*.py" | head -20
   ```
   - Search for class definitions: `grep -rn "class ClassName"` — NOT `ClassName.method`
   - Search for function definitions: `grep -rn "def method_name"` — NOT `obj.method_name`
   - If result is empty, try a DIFFERENT keyword — NEVER repeat the same search
   - NEVER use `find . -name` — NEVER use `python -c "import pkg; print(pkg.__file__)"`

3. **Read only the relevant section:**
   ```
   grep -n "feature_name\|method_name" /path/to/file.py
   sed -n '50,80p' /path/to/file.py
   ```

## Phase 2 — Pattern Analysis

- Find a similar existing feature in the same file/class
- Copy its pattern exactly — do not invent a new style
- Check how the existing method is called elsewhere:
  `grep -n "method_name(" /path/to/file.py`
- Understand what the existing code does before touching it

## Phase 3 — Plan the Change

- State clearly: "I will add X by changing Y at line Z"
- Use backward-compatible defaults so existing callers do not break
- ONE change at a time — do not bundle multiple features

## Phase 4 — Implement

Apply the fix:
- Simple one-line change: `sed -i '' 's/old/new/' /path/to/file.py`
- Multi-line or special characters: use Python:
  ```
  python3 -c "c=open('/path/to/file.py').read(); open('/path/to/file.py','w').write(c.replace('old','new'))"
  ```

Verify: `grep -n "new_feature" /path/to/file.py`

Submit immediately — do not refactor, document, or add tests.

## CRITICAL: Edit the actual file on disk

- Do NOT just run `python -c` to test in memory — that does not change the file
- Do NOT just print the fix — you must write it to the file
- For simple changes use `sed -i ''`; for multi-line/complex use Python as above

## Common Feature Patterns

### Add a parameter to an existing method
- Find the method signature, add new param with a default: `def method(self, ..., new_param=None)`
- Inside the method, branch on it: `if new_param is not None: ...`

### Add file mode / open() control
- Replace `open(path, "r")` with `open(path, mode)` where `mode` defaults to `"r"`

### Add validation / raise on bad input
- Find where the value is first used, add a guard before it:
  `if bad_condition: raise ValueError(f"...")`
- Match the existing raise style in the file

### Add case-insensitive matching
- Wrap the comparison: `value.upper()` or use `re.IGNORECASE`

### Expose a new attribute or version tuple
- Find where `__version__` is defined
- Add the new attribute next to it, parsing the version string if needed

### Extend repr / string output
- Find the `__repr__` or formatting function
- Add the new field following the same format as adjacent fields

## Key Rules

- Do NOT change function signatures of public APIs except to add an optional param
- Do NOT add new imports unless the feature strictly requires them
- If the issue description shows the exact code change needed, implement it literally

## Red Flags — Return to Phase 1

- Repeating the same grep that already returned nothing
- Adding a parameter without reading how the method is called
- Touching more than one function for a single feature addition

## Submission

When done, run exactly:
```
echo COMPLETE_TASK_AND_SUBMIT_FINAL_OUTPUT
```

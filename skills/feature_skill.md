# Python Feature Addition Skill

## Strategy
1. Identify a unique keyword from the issue: the class name, method name, or feature being extended.
   Search for the relevant file by that keyword:
   `grep -rn "unique_keyword" . --include="*.py" | head -20`
   - Search for class definitions: `grep -rn "class ClassName"` not `ClassName.method`
   - Search for function definitions: `grep -rn "def method_name"` not `obj.method_name`
   - If result is empty, try a DIFFERENT keyword — never repeat the same search twice
   NEVER guess a filename with `find . -name` — NEVER use `python -c "import pkg; print(pkg.__file__)"`.
2. Do NOT cat the whole file — use grep to find the relevant section:
   `grep -n "feature_name\|method_name" /real/path/to/file.py`
   Then read only that section: `sed -n '50,80p' /real/path/to/file.py`
3. Find a similar existing feature in the same file/class — copy its pattern exactly
4. Edit the file:
   - Simple one-line change: `sed -i '' 's/old_code/new_code/' /real/path/to/file.py`
   - Multi-line or special characters (quotes, f-strings): use Python:
     `python3 -c "c=open('/real/path/to/file.py').read(); open('/real/path/to/file.py','w').write(c.replace('old','new'))"`
5. Verify the change: `grep -n "new_feature" /real/path/to/file.py`
6. Use backward-compatible defaults so nothing breaks (new param defaults to old behavior)
7. Submit immediately — do not refactor, document, or add tests unless asked

## CRITICAL: You MUST edit the actual file on disk
- Do NOT just run `python -c` to test in memory — that does not change the file
- Do NOT just print the fix — you must write it to the file
- For simple changes use `sed -i ''`; for complex/multi-line changes use Python as shown in Strategy above

## Common Feature Patterns

### Add a parameter to an existing method
- Find the method signature and add the new param with a default: `def method(self, ..., new_param=None)`
- Inside the method, branch on it: `if new_param is not None: ...`
- Check how the method is called elsewhere (`grep -n "method_name("`) to confirm you don't break callers

### Add file mode / open() control
- Replace `open(path, "r")` with `open(path, mode)` where `mode` defaults to `"r"`
- Pass the mode param through from the outer function

### Add validation / raise on bad input
- Find where the value is first used, add a guard before it:
  `if bad_condition: raise ValueError(f"...")`
- Look at existing `raise` patterns in the file for the right exception type and message style

### Add case-insensitive matching
- Wrap the comparison: `value.upper()` or use `re.IGNORECASE`
- Find the exact line doing the comparison with `grep -n` first

### Extend repr / string output
- Find the `__repr__` or formatting function
- Add the new field following the same format as adjacent fields

### Expose a new attribute or version tuple
- Find where `__version__` is defined
- Add the new attribute next to it, parsing the version string if needed

## Key Rules
- Do NOT change function signatures of public APIs except to add an optional param
- Do NOT add new imports unless the feature strictly requires them
- If the issue description shows the exact code change needed, implement it literally

## Submission
When done, run exactly:
```
echo COMPLETE_TASK_AND_SUBMIT_FINAL_OUTPUT
```

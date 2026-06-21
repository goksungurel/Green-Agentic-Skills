# Python Feature Addition Skill

## Strategy
1. Find the package path first: `python -c "import package_name; print(package_name.__file__)"`
2. Find a similar existing feature in the same file/class — copy its pattern exactly
3. Implement minimally: add the parameter/method, wire it up, done
4. Use backward-compatible defaults so nothing breaks (new param defaults to old behavior)
5. Submit immediately — do not refactor, document, or add tests unless asked

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

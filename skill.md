# Python Debugging Skill

## Strategy
When fixing a Python bug, follow this exact order:
1. Read the error message and identify the file + line number
2. Read that file to understand the context (use `cat` or `grep`)
3. Make ONE minimal, targeted fix
4. Verify the fix makes logical sense before submitting
5. Submit immediately — do not explore unrelated code

## Rules
- Do NOT refactor or clean up unrelated code
- Do NOT add new features
- Do NOT change function signatures unless the bug requires it
- Fix ONLY what the issue description explicitly describes
- Prefer editing existing code over rewriting from scratch

## Common Bug Patterns

### AttributeError
- Check if the object could be None before accessing its attributes
- Verify the attribute name spelling matches the class definition

### TypeError
- Check that argument types match the function signature
- Watch for None being passed where a concrete value is expected

### ImportError / ModuleNotFoundError
- Verify the import path matches the actual module structure
- Check for circular imports

### KeyError
- Use `.get(key, default)` instead of `dict[key]` when key may be missing
- Verify the key exists with `key in dict` before accessing

### ValueError
- Validate inputs before passing them to functions
- Check for empty sequences before indexing

### IndexError
- Check list length before accessing by index
- Use negative indexing carefully

## Workflow Example
```
1. grep -n "error_function" src/module.py   # locate the problem
2. cat src/module.py | head -50             # read context
3. sed -i 's/old_code/new_code/' src/module.py  # apply fix
4. echo COMPLETE_TASK_AND_SUBMIT_FINAL_OUTPUT
```

## Submission
When the fix is complete, run exactly:
echo COMPLETE_TASK_AND_SUBMIT_FINAL_OUTPUT

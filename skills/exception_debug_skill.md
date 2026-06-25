# Exception Debugging Skill

## Strategy
1. Read the traceback — identify the exception type and the exact failing line
2. Find the file in the local repo with find: `find . -name "filename.py"`
   NEVER use `python -c "import pkg; print(pkg.__file__)"` — that finds the installed package, not the local file.
   Never use a placeholder path — always use the exact path from find output.
3. Do NOT cat the whole file — use grep to find the relevant lines:
   `grep -n "failing_function_name" /real/path/to/file.py`
4. Read only the relevant section: `sed -n '50,80p' /real/path/to/file.py`
5. Edit the file with sed: `sed -i '' 's/old_code/new_code/' /real/path/to/file.py`
6. Verify the change: `grep -n "failing_function" /real/path/to/file.py`
7. Submit immediately

## CRITICAL: You MUST edit the actual file on disk
- Do NOT just run `python -c` to test in memory — that does not change the file
- Do NOT just print the fix — you must write it to the file
- Use `sed -i` or `cat > file.py << 'EOF'` to apply the fix to the actual file

## Exception Patterns and Fixes

### TypeError: unsupported operand / wrong type
- Check if a value can be `None` before operating on it
- Patch: `if value is None: return ...` or `value = value if value is not None else default`
- Boolean data causing arithmetic: cast to numeric first (`data.astype(float)`)

### TypeError: got an unexpected keyword argument
- The argument doesn't exist in this version — check the actual method signature with `grep -n "def method_name"` before adding a parameter

### IndexError: index out of bounds
- The array has fewer elements than expected — check the shape before indexing
- Fix: remove or guard the out-of-bounds line; do not resize the array

### ValueError: X is not invertible / X cannot be done
- Wrap the failing call in `try/except` and return a sensible fallback
- Example: `try: result = norm.inverse(v) except ValueError: result = np.nan`

### LinAlgError / SVD did not converge
- Input data contains `NaN` or `None` — filter before numeric operations
- Fix: `data = data.dropna()` or `mask = np.isfinite(x) & np.isfinite(y); x, y = x[mask], y[mask]`

### Exception not wrapped (passes through as wrong type)
- A low-level exception (socket.error, urllib3 error) escapes unwrapped
- Fix: catch it alongside existing exceptions and re-raise as the correct type
- Example: `except (socket.error, existing_error) as e: raise RequestException(e)`

## Submission
When the fix is complete, run exactly:
```
echo COMPLETE_TASK_AND_SUBMIT_FINAL_OUTPUT
```

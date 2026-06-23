# Exception Debugging Skill

## Strategy
1. Read the traceback — identify the exception type and the exact failing line
2. Find the package path: `python -c "import package_name; print(package_name.__file__)"`
3. Go directly to the failing line — do not explore unrelated code
4. Make ONE minimal fix
5. Submit immediately

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

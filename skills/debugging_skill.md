# Python Debugging Skill

## Strategy
1. Read the error message — identify the exception type and the module name (e.g. `seaborn._core.scales`)
2. Find the package path: `python -c "import package_name; print(package_name.__file__)"`
3. Search in that directory: `grep -rn "function_name" /found/path/`
4. Read only the relevant code section, make ONE minimal fix
5. Submit immediately — do not explore unrelated code

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

### Logic bug — wrong result, no exception
- Read the description's expected vs actual output carefully
- Grep for the specific function name to find the exact line
- Common causes: wrong variable used, missing `.copy()`, in-place op not assigned, regex matching only last line

### Regression bug — worked in version X, broken in version Y
- The fix is almost always a one-line guard for the new edge case
- Find where the behavior diverged: look for `if ... is None` or missing fallback

## Submission
When the fix is complete, run exactly:
```
echo COMPLETE_TASK_AND_SUBMIT_FINAL_OUTPUT
```

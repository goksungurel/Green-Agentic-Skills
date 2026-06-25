# Logic / Silent Bug Debugging Skill

## Strategy
1. Read the description's expected vs actual output carefully — there is NO exception
2. Find the file in the local repo with find: `find . -name "filename.py"`
   NEVER use `python -c "import pkg; print(pkg.__file__)"` — that finds the installed package, not the local file.
   Never use a placeholder path — always use the exact path from find output.
3. Do NOT cat the whole file — it may be too long. Use grep to find the relevant lines:
   `grep -n "keyword_from_description" /real/path/to/file.py`
   `grep -n "replace\|encode_ascii" /real/path/to/file.py`
4. Read only the relevant section: `sed -n '100,130p' /real/path/to/file.py`
5. Edit the file directly with sed: `sed -i '' 's/old_code/new_code/' /real/path/to/file.py`
6. Verify the change: `grep -n "keyword" /real/path/to/file.py`
7. Submit immediately

## CRITICAL: You MUST edit the actual file on disk
- Do NOT just run `python -c` to test in memory — that does not change the file
- Do NOT just print the fix — you must write it to the file
- Use `sed -i` or `cat > file.py << 'EOF'` to apply the fix to the actual file

## Bug Patterns and Fixes

### Return value not assigned (silent no-op)
- Symptoms: operation runs without error but has no effect
- Cause: method returns a NEW object instead of modifying in-place, result is discarded
- Common culprits: `str.replace()`, `bytes.replace()`, `chararray.replace()`, `re.sub()`, `.strip()`
- Wrong: `obj.replace(a, b)` — Right: `obj = obj.replace(a, b)`
- How to find: grep for the method name, check if result is assigned back

### Logic bug — SIMPLE function (< 30 lines)
- Grep for the specific function name to find the exact line
- Common causes: wrong variable used, missing `.copy()`, regex matching only last line
- Fix: change the one wrong line — do not restructure the function

### Algorithmic bug — COMPLEX function (> 30 lines)
- Do NOT grep and guess — read the full function first
- Step 1: reproduce with exact example from description
  `python -c "from package import func; print(func(example_input))"`
- Step 2: add temporary print statements to find where output diverges
- Step 3: the description usually names the broken sub-case (e.g. "nested models", "3+ objects", "single-dim")
- Step 4: find the conditional branch or recursive call that handles that sub-case
- Fix: fix only that branch — one or two lines at most
- Remove temporary print statements before submitting

### Side effect bug (operation changes state it shouldn't)
- Symptoms: calling function X unexpectedly modifies unrelated state Y
- How to find: grep for what state Y is and where it gets modified
- Fix: add a guard so X does not touch Y, or save/restore Y around the call

### Missing feature check / wrong condition
- Symptoms: code runs but ignores a flag or feature that should change its behavior
- How to find: grep for the flag name or the feature attribute
- Fix: add `if connection.features.flag:` guard or equivalent — one line

## Submission
When the fix is complete, run exactly:
```
echo COMPLETE_TASK_AND_SUBMIT_FINAL_OUTPUT
```

"""
dedup_agent.py
--------------
A thin subclass of mini-swe-agent's DefaultAgent that adds ONE harness-level
guard: it stops the model from burning its entire step budget by re-issuing
the exact same shell command after that command already returned an
unproductive result — either empty output, or a failed/error result
(non-zero returncode, e.g. a shell syntax error).

## Why this exists

Trajectory inspection of round-2 validation's LimitsExceeded runs (4/4 of
them) showed the model issuing a byte-identical command for every single
step of a 25-step run, e.g.:

    grep -rn "def sqlmigrate" . --include="*.py" | head -20

...always with the same empty `{"returncode": 0, "output": ""}` result.
Conversation history was confirmed to accumulate correctly (53 messages,
all prior empty attempts visible) — so the model COULD see it was repeating
itself, but did not adapt. mini.yaml's existing prompt rule
("NEVER repeat a failed command") was already being completely ignored in
these cases, so a prompt-only rewrite is unlikely to close this gap (same
conclusion as the earlier verify-step-skip finding).

## Blind spot found and closed (validate_dedup_fix.py run13, pydata__xarray-3364)

The original version of this guard only treated a repeat as unproductive
when the PREVIOUS attempt's output was empty/whitespace-only. Trajectory
inspection of run13 (LimitsExceeded) showed the model issuing the exact
same broken `python3 -c "..."` one-liner (a quoting mismatch — nested
single/double quotes plus an embedded multi-line replacement string)
~17 times in a row, every time getting the identical bash
`syntax error near unexpected token` (returncode 2, non-empty stderr
text). Because that output is non-empty, `_last_output_was_empty` was
always False, so the guard never engaged — same stuck-repetition
phenomenon as the original bug, just routed around the guard's narrower
trigger condition. Generalized the trigger to "previous attempt was
unproductive" = empty output OR non-zero returncode, since a command that
already failed deterministically will fail identically again for the same
reason this project already accepts for empty output (nothing in the repo
or the command string changed between attempts).

## What this does NOT do

- Does not look at task content, the issue text, or which file/keyword is
  involved. It only ever compares a command string to the immediately
  preceding command string.
- Does not change the model's actual editing/search strategy or give it any
  domain hints.
- Does not suppress "unproductive turns" in general — a model that explores
  several DIFFERENT empty searches in a row is untouched; only an EXACT
  repeat of a command that already returned empty output is intercepted.
- Applies identically to every condition (baseline and all 3 skill files) —
  it is loaded via --agent-class for every run in experiment.py, regardless
  of condition.

## What this does

1st occurrence of a command: executed normally, no change in behavior.

If that exact command is issued again immediately afterward AND the first
attempt's output was empty/whitespace-only: the command is NOT re-executed
(deterministic repo state -> it would just return empty again). Instead the
model receives a synthetic tool observation, in the same JSON shape the
normal observation_template produces, telling it plainly that it already
ran this and got nothing, and listing a few generic (non-task-specific)
alternative strategies.

If the model repeats the SAME command a third time in a row (i.e. ignores
the corrective message too): the run is aborted immediately with
exit_status="StuckRepetition", instead of silently consuming the rest of
the step budget on a no-op loop. This is intentionally a DIFFERENT
exit_status than "LimitsExceeded" so reporting can distinguish "ran out of
steps while making genuine progress" from "got stuck in a deterministic
loop and was cut off early" — these are different failure modes and were
previously conflated.
"""

import subprocess

from minisweagent.agents.default import DefaultAgent
from minisweagent.exceptions import InterruptAgentFlow

_SUBMIT_KEYWORD = "COMPLETE_TASK_AND_SUBMIT_FINAL_OUTPUT"

_EMPTY_DIFF_TEXT = (
    "[dedup-guard] Submit blocked: `git diff HEAD` is empty — no file in the "
    "repository has actually changed. Your edit command may have run without "
    "error but the target string was not found in the file (silent no-op). "
    "Do NOT submit yet. Go back, re-read the file to find the exact string "
    "that needs to change, then apply a fresh edit and verify with "
    "`git diff HEAD` before submitting."
)

_NUDGE_TEXT = (
    "[dedup-guard] You already ran this exact command and it did not produce "
    "a usable result (either empty output, or a failed/error result). "
    "Running it again will not produce a different result, because nothing "
    "about the command or the repository has changed since the last "
    "attempt. If it returned empty: try a genuinely different command — a "
    "different search keyword from the issue text, a different file, "
    "`grep -il` for case-insensitive matching, or an `ls`/`find`-style "
    "directory listing. If it errored (e.g. a shell syntax error from "
    "quoting): simplify the command — avoid nesting both single and double "
    "quotes or multi-line strings inside a single `python3 -c \"...\"` "
    "call, and consider writing the edit in smaller, separate steps."
)


class StuckRepetition(InterruptAgentFlow):
    """Raised when the agent issues the same exact command 3x in a row,
    each time after the previous attempt already returned an unproductive
    result (empty output, or a failed/error result)."""


class DedupAgent(DefaultAgent):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._last_command: str | None = None
        self._last_output_was_unproductive: bool = False
        self._repeat_streak: int = 0

    @staticmethod
    def _is_unproductive(output: dict) -> bool:
        """Empty/whitespace-only output, or a non-zero returncode (error,
        e.g. a shell syntax error) — either way, repeating the exact same
        command will deterministically produce the same unusable result."""
        if output.get("returncode", 0) != 0:
            return True
        return not output.get("output", "").strip()

    @staticmethod
    def _git_diff_empty() -> bool:
        """Return True if git diff HEAD has no output (no real file changes)."""
        try:
            result = subprocess.run(
                ["git", "diff", "HEAD"],
                capture_output=True, text=True, timeout=10,
            )
            return not result.stdout.strip()
        except Exception:
            return False  # if git fails for any reason, don't block the submit

    def execute_actions(self, message: dict) -> list[dict]:
        actions = message.get("extra", {}).get("actions", [])
        outputs = []
        for action in actions:
            command = (action.get("command") or "").strip()

            # --- Submit guard: block submit when diff is empty ---------------
            if _SUBMIT_KEYWORD in command and self._git_diff_empty():
                outputs.append({
                    "output": _EMPTY_DIFF_TEXT,
                    "returncode": 1,
                    "exception_info": "",
                })
                # Reset repeat tracking so a fresh real command isn't penalised
                self._last_command = None
                self._last_output_was_unproductive = False
                self._repeat_streak = 0
                continue
            # -----------------------------------------------------------------

            is_repeat_of_unproductive = bool(
                command
                and command == self._last_command
                and self._last_output_was_unproductive
            )
            self._repeat_streak = self._repeat_streak + 1 if is_repeat_of_unproductive else 0

            if self._repeat_streak == 0:
                # Normal execution path — identical to DefaultAgent.
                output = self.env.execute(action)
                self._last_command = command
                self._last_output_was_unproductive = self._is_unproductive(output)
            elif self._repeat_streak == 1:
                # First repeat of an unproductive command: don't re-run it,
                # just nudge. Keep _last_command/_last_output_was_unproductive
                # as-is so a third identical attempt is still recognized.
                output = {"output": _NUDGE_TEXT, "returncode": 1, "exception_info": ""}
            else:
                # Second repeat (third identical command in a row) — abort.
                raise StuckRepetition(
                    self.model.format_message(
                        role="exit",
                        content="StuckRepetition: identical command issued 3x in a row, each time after an unproductive (empty or failed) result.",
                        extra={"exit_status": "StuckRepetition", "submission": ""},
                    )
                )
            outputs.append(output)

        return self.add_messages(
            *self.model.format_observation_messages(message, outputs, self.get_template_vars())
        )

"""
Executes the two AI-initiated actions that touch the outside world:

  - run_command()        -- runs a PowerShell command via pwsh.exe
  - read_arbitrary_file() -- reads a file from anywhere on disk

Both are only ever called from main.py AFTER the user has explicitly
confirmed the action (see _confirm_action / _run_ai_action_loop in main.py).
Nothing in this module executes or reads anything on its own.
"""

import os
import subprocess

PWSH_TIMEOUT = 60  # seconds -- keeps a hung/interactive command from freezing the session
MAX_OUTPUT_CHARS = 4000
MAX_READ_CHARS = 8000


def run_command(command: str, cwd: str = None, timeout: int = PWSH_TIMEOUT):
    """
    Run `command` through pwsh.exe. Returns (success: bool, output: str).
    `output` combines stdout and stderr (stderr labeled), truncated to a
    sane length before it gets handed back to the AI as context.
    """
    if not command or not command.strip():
        return False, "no command given"

    args = ["pwsh.exe", "-NoProfile", "-NonInteractive", "-Command", command]

    try:
        result = subprocess.run(
            args,
            cwd=cwd if cwd and os.path.isdir(cwd) else None,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except FileNotFoundError:
        return False, "pwsh.exe not found on PATH -- is PowerShell 7+ installed?"
    except subprocess.TimeoutExpired:
        return False, f"command timed out after {timeout}s"
    except Exception as e:
        return False, f"failed to run command: {e}"

    output = (result.stdout or "").rstrip()
    if result.stderr:
        output += ("\n" if output else "") + f"[stderr] {result.stderr.rstrip()}"
    output = output.strip() or "(no output)"

    if len(output) > MAX_OUTPUT_CHARS:
        cut = len(output) - MAX_OUTPUT_CHARS
        output = output[:MAX_OUTPUT_CHARS] + f"\n...[truncated, {cut} more characters]"

    return result.returncode == 0, output


def read_arbitrary_file(path: str, max_chars: int = MAX_READ_CHARS):
    """
    Read a text file from anywhere on disk (not limited to file_handler's
    INPUT_DIRS -- that's the point of this directive). Returns
    (success: bool, content_or_error: str). Binary files are rejected: this
    feeds a chat prompt, not a byte pipe.
    """
    if not path:
        return False, "no path given"
    if not os.path.isfile(path):
        return False, f"file not found: {path}"

    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            content = f.read()
    except Exception as e:
        return False, f"error reading file: {e}"

    if len(content) > max_chars:
        cut = len(content) - max_chars
        content = content[:max_chars] + f"\n...[truncated, {cut} more characters]"

    return True, content
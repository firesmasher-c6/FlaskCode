"""
Executes AI-initiated actions that touch the outside world:

  - run_command()          -- runs a bash command
  - read_arbitrary_file()  -- reads a file from anywhere on disk

Both are only ever called AFTER the user has explicitly confirmed the
action via the API. Nothing here executes on its own.

Linux-only: PowerShell/cmd/pwsh executors are not supported.
"""

import os
import subprocess

BASH_TIMEOUT = 60      # seconds
MAX_OUTPUT_CHARS = 4000
MAX_READ_CHARS = 8000


def run_command(command: str, cwd: str = None, executor: str = None, timeout: int = BASH_TIMEOUT):
    """
    Run `command` through bash. `executor` is accepted for API compatibility
    but only 'bash' / 'bash.exe' / None are valid on Linux.
    Returns (success: bool, output: str).
    """
    if not command or not command.strip():
        return False, "no command given"

    executor = (executor or "bash").lower().strip()
    if executor not in ("bash", "bash.exe", "sh"):
        return False, f"executor '{executor}' is not supported on Linux — use bash"

    args = ["bash", "-c", command]

    try:
        result = subprocess.run(
            args,
            cwd=cwd if cwd and os.path.isdir(cwd) else None,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except FileNotFoundError:
        return False, "bash not found on PATH"
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
    Read a text file from anywhere on disk. Returns (success: bool, content_or_error: str).
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

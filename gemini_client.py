import json
import os
import random
import re
import sqlite3
import time
import urllib.request
import urllib.error

import yaml

import apikey_settings

API_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-3.1-flash-lite:generateContent"
KEYS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".apikeys")
DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "knowledge.db")

_PLACEHOLDER_RE = re.compile(r'^KEY\d+$', re.IGNORECASE)
_VALID_KEY_RE = re.compile(r'^(AI[A-Za-z0-9_-]{10,}|AQ\.[A-Za-z0-9_-]{10,})$')
_PLACEHOLDER_VALUE = "YOUR_API_KEY_HERE"
_SLOTS = (1, 2, 3)

# ---------------------------------------------------------------------------
# .apikeys format (YAML, keyed by slot -- these slot numbers are exactly the
# ones /apikey <1|2|3> and apikey_settings.py refer to):
#
#   key_1: "AIza..."
#   key_2: "YOUR_API_KEY_HERE"
#   key_3: "YOUR_API_KEY_HERE"
#
# Empty/placeholder slots are skipped when picking a key to use. If an old
# (pre-YAML, one-raw-key-per-line) .apikeys file is found instead, it's
# migrated to this format automatically the first time it's read.
# ---------------------------------------------------------------------------


def _strip_custom_comments(text: str) -> str:
    """Removes any custom '-! COMMENT' sections from the text."""
    return re.sub(r'-!.*$', '', text, flags=re.MULTILINE)


def _is_placeholder(value) -> bool:
    if value is None:
        return True
    if not isinstance(value, str):
        return False
    v = value.strip()
    if not v or v.upper() == _PLACEHOLDER_VALUE:
        return True
    return bool(_PLACEHOLDER_RE.match(v))


def _parse_yaml_keys(data) -> list:
    """Given a parsed YAML dict (key_1/key_2/key_3 -> value), return the
    populated, valid-looking [(label, key), ...] pairs in slot order."""
    if not isinstance(data, dict):
        return []
    keys = []
    for i in _SLOTS:
        raw = data.get(f"key_{i}")
        if _is_placeholder(raw):
            continue
        value = str(raw).strip()
        if not _VALID_KEY_RE.match(value):
            continue
        keys.append((f"KEY{i}", value))
    return keys


def _extract_legacy_keys(raw_text: str) -> list:
    """Pull real-looking API keys, in order, out of an old-format (one raw
    key per line, optional '%...%' wrapping, '-!' comments) .apikeys file."""
    found = []
    for raw_line in raw_text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("-!") or line.startswith("#"):
            continue
        line = line.strip('%').strip()
        if not line or _PLACEHOLDER_RE.match(line):
            continue
        if _VALID_KEY_RE.match(line) and line not in found:
            found.append(line)
    return found


def _write_yaml_keys(real_keys: list) -> bool:
    """Write .apikeys in the key_1/key_2/key_3 YAML format. `real_keys` is a
    list of up to 3 real key strings, assigned to key_1.. in order; any
    slots beyond what was given are filled with the placeholder."""
    slots = {
        f"key_{i}": (real_keys[i - 1] if i - 1 < len(real_keys) else _PLACEHOLDER_VALUE)
        for i in _SLOTS
    }
    try:
        with open(KEYS_FILE, "w", encoding="utf-8") as f:
            yaml.dump(slots, f, default_flow_style=False, sort_keys=False)
        return True
    except Exception:
        return False


def needs_migration() -> bool:
    """True if .apikeys exists but isn't yet in the key_1/key_2/key_3 YAML
    format. Used by main.py to decide whether to show the migration UX."""
    if not os.path.exists(KEYS_FILE):
        return False
    try:
        with open(KEYS_FILE, "r", encoding="utf-8") as f:
            raw_text = f.read()
    except Exception:
        return False
        
    raw_text = _strip_custom_comments(raw_text)
    
    try:
        parsed = yaml.safe_load(raw_text)
    except Exception:
        parsed = None
    return not (isinstance(parsed, dict) and any(f"key_{i}" in parsed for i in _SLOTS))


def migrate_apikeys_file() -> bool:
    """
    Actually perform the legacy -> YAML migration right now (no printing or
    delay -- that's main.py's job so it can show its own timed messages).
    Returns True on success (including "nothing to migrate"), False if the
    file couldn't be read/written.
    """
    if not os.path.exists(KEYS_FILE):
        return True
    try:
        with open(KEYS_FILE, "r", encoding="utf-8") as f:
            raw_text = f.read()
    except Exception:
        return False
        
    raw_text = _strip_custom_comments(raw_text)
    
    legacy_keys = _extract_legacy_keys(raw_text)
    return _write_yaml_keys(legacy_keys[:3])


def _migrate_legacy_file_if_needed():
    """
    Silent, instant safety-net migration used internally by _load_api_keys()
    in case something calls it before main.py's own (printed/timed)
    migration step has run. No-op if already migrated, missing, or unreadable.
    """
    if needs_migration():
        migrate_apikeys_file()


def _load_api_keys(max_keys: int = None) -> list:
    """
    Load API keys from the .apikeys YAML file (key_1/key_2/key_3 slots),
    migrating an old-format file automatically if one is found. Placeholder
    ("YOUR_API_KEY_HERE") and malformed slots are skipped. GEMINI_API_KEY
    from the environment, if set, is appended as an extra candidate.

    Returns a list of (label, key) tuples, e.g. [("KEY1", "AIza..."), ("KEY3", "AQ...")],
    where label is the slot name ("KEY1"/"KEY2"/"KEY3") or "ENV" for a key
    sourced from the environment variable. There is no cap on how many keys
    can be loaded unless `max_keys` is explicitly given.
    """
    _migrate_legacy_file_if_needed()

    keys = []
    seen = set()

    if os.path.exists(KEYS_FILE):
        try:
            with open(KEYS_FILE, "r", encoding="utf-8") as f:
                raw_text = f.read()
                raw_text = _strip_custom_comments(raw_text)
                data = yaml.safe_load(raw_text)
            for label, key in _parse_yaml_keys(data):
                if key in seen:
                    continue
                seen.add(key)
                keys.append((label, key))
                if max_keys is not None and len(keys) >= max_keys:
                    break
        except Exception:
            pass

    env_key = os.environ.get("GEMINI_API_KEY")
    if env_key and env_key.strip() and env_key.strip() not in seen:
        keys.append(("ENV", env_key.strip()))

    return keys


def _mask_key(key: str) -> str:
    """Redact the middle of a key for safe display (used by debug mode)."""
    if not key:
        return "(none)"
    if len(key) <= 10:
        return key[:2] + "…" + key[-2:]
    return key[:6] + "…" + key[-4:]


def _pick_api_key():
    """Randomly select one of the configured (label, key) pairs. Returns None if none are set."""
    keys = _load_api_keys()
    if not keys:
        return None
    return random.choice(keys)


def has_api_key(username: str = None):
    return len(_load_api_keys()) > 0


def key_status_label(username: str = None):
    """
    Return a short phase label describing what ask() will actually do for
    this user right now, or None if no keys are configured at all:
      - a locked-in slot (/apikey <1|2|3>) is set for this user -> "using saved key"
      - more than one usable key and nothing locked in          -> "choosing apikey"
      - exactly one usable key overall                          -> "using apikey"
    """
    keys = _load_api_keys()
    if not keys:
        return None

    if username:
        selected_index = apikey_settings.get_selected_key(username)
        if selected_index is not None:
            return "using saved key"

    return "choosing apikey" if len(keys) > 1 else "using apikey"


def ping(timeout: int = 5, username: str = None):
    """
    Check whether the Gemini API is reachable, without spending a prompt.
    Hits the models-list endpoint (metadata only, no generateContent call).
    Returns (ok: bool, message: str).
    """
    picked = _pick_api_key()
    if not picked:
        return False, "no API key found (set GEMINI_API_KEY or create .apikeys)"
    label, api_key = picked

    list_url = "https://generativelanguage.googleapis.com/v1beta/models"
    req = urllib.request.Request(
        list_url,
        method="GET",
        headers={"x-goog-api-key": api_key},
    )

    start = time.time()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            resp.read(1)  # touch the connection, discard the body
            status = resp.status
    except urllib.error.HTTPError as e:
        elapsed = time.time() - start
        if e.code in (401, 403):
            return False, f"reachable but API key rejected ({e.code}) via {label} in {elapsed:.2f}s"
        return False, f"HTTP error {e.code} via {label} in {elapsed:.2f}s"
    except urllib.error.URLError as e:
        return False, f"unreachable: {e.reason}"
    except Exception as e:
        return False, f"unexpected error: {e}"

    elapsed = time.time() - start
    return True, f"reachable ({status}) via {label} in {elapsed:.2f}s"


def _get_learned_knowledge(max_phrases: int = 15):
    """Extract most frequently-seen bigrams and interesting topic words from knowledge.db."""
    if not os.path.exists(DB_PATH):
        return []
    
    try:
        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        
        # Get top bigrams (w1 w2) sorted by weight
        cur.execute("""
            SELECT w1, w2, weight FROM chain 
            WHERE w2 != '<END>'
            ORDER BY weight DESC 
            LIMIT ?
        """, (max_phrases,))
        
        phrases = []
        for w1, w2, weight in cur.fetchall():
            phrases.append(f"{w1} {w2}")
        
        conn.close()
        return phrases
    except:
        return []


def build_prompt(user_message: str, context: dict) -> str:
    lines = [
        "You are Flask Code. You are not an AI yourself; you transform an AI into an AI agent that can run actions on behalf of the user.",
        "You have a local knowledge base of learned words and phrases. Use the notes below as "
        "flavor and context, but respond naturally in your own words -- do not copy them verbatim.",
    ]
    
    # Identify who's actually talking to it
    if context.get("username"):
        if context.get("is_admin"):
            lines.append(f'You are talking to {context["username"]}, the administrator of this Flask Code app.')
        else:
            lines.append(f'You are talking to {context["username"]}, a regular (non-admin) user.')

    # Add persistent per-user "remember this about me" notes if available
    if context.get("saved_info"):
        lines.append(context["saved_info"])

    # Add chat history if available
    if context.get("chat_history"):
        lines.append(context["chat_history"])
    
    # Add learned knowledge from database
    learned = _get_learned_knowledge(max_phrases=15)
    if learned:
        lines.append(f"Knowledge from memory: {', '.join(learned)}.")
    
    if context.get("topic_words"):
        lines.append(f"Relevant words from this conversation: {', '.join(context['topic_words'])}.")
    
    if context.get("drafts"):
        lines.append("Internal thought drafts (inspiration, not to be copied exactly):")
        for d in context["drafts"]:
            lines.append(f"  - {d}")

    # Results of any action(s) the AI requested on a previous round of this
    # exchange (see the directive system below) -- present if this is a
    # follow-up call after a --pwsh.exe / -rd request was executed.
    if context.get("tool_results"):
        lines.append("Results from action(s) you requested a moment ago:")
        for r in context["tool_results"]:
            lines.append(f"  - {r}")
        lines.append(
            "Use these results to give your real answer now. Don't request the same "
            "action again unless it's genuinely necessary."
        )

    lines.append(
        "You have three special action directives available, each written as the very "
        "first non-blank line inside a fenced code block ('#' is used for this line even "
        "in languages that don't normally comment with it):\n"
        "  0. Only ask the user which CLI to use when they explicitly ask you to run something "
        "and the shell choice matters. If they did not ask for execution, do not ask about CLI at all; "
        "use the most likely shell for the environment (typically PowerShell/pwsh on Windows).\n"
        "  1. Run a shell command and ask permission before executing it:\n"
        "     # --cmd.exe -c\"<command>\" -ask\n"
        "     # --powershell.exe -c\"<command>\" -ask\n"
        "     # --pwsh.exe -c\"<command>\" -ask\n"
        "     # --bash -c\"<command>\" -ask\n"
        "     # --bash.exe -c\"<command>\" -ask\n"
        "     Add -path\"<directory>\" if it needs to run in a specific folder. The user must be asked to approve before anything runs, and the command's output will be given back to you.\n"
        "  2. Write a file directly (only when the user actually wants a real file, not just "
        "a snippet to look at):\n"
        "     # --FileName yourfilename.ext -gen -write\n"
        "     followed by the file's full contents as the rest of the block.\n"
        "  3. Read an existing file from disk:\n"
        "     # --FileName label.ext -rd -path\"C:\\full\\path\\to\\file\"\n"
        "     The user will be asked to approve, and the file's contents will be given back "
        "to you.\n"
        "These directive lines must be the first thing in the fence, and a block should only "
        "ever carry one of them. For any other code -- examples, snippets to discuss, anything "
        "the user didn't ask you to save or run -- do NOT add a directive line at all. Just "
        "show the code plainly; the terminal will separately ask the user if they want to keep it.\n"
        "If you want to see the list of a directory, run `dir` in the chosen shell instead of using a file-read directive like `# --FileRead -c""COMMAND"" -rd ....`\n"
        "Do not try to read a directory as if it were a file."
    )
    
    lines.append(
        "Format your replies in markdown often -- **bold** for emphasis, `inline code` for "
        "identifiers/commands, fenced code blocks for anything multi-line, bullet/numbered "
        "lists for steps or options, and headers for longer answers. Don't force it into short "
        "one-line replies, but reach for it by default rather than plain prose."
    )

    lines.append(f'User said: "{user_message}"')
    lines.append("Reply with precision")
    return "\n".join(lines)


def ask(user_message: str, context: dict, model: str = "3.1-flash-lite", timeout: int = 200):
    """
    Returns (answer_text, error_message, debug_info). Exactly one of
    answer_text/error_message will be None.

    debug_info is a dict: {"used_label": str|None, "used_key_masked": str|None,
    "attempts": [labels tried, in order]}, or None if no keys were configured
    at all (nothing was attempted).

    Normally, if a key fails (HTTP error, network error, malformed response,
    etc.), the remaining configured keys are tried in turn before giving up.
    EXCEPTION: if the current user has permanently locked in a key via
    /apikey <1|2|3> (see apikey_settings), only that key is ever tried --
    no fallback to the others if it fails.
    """
    keys = _load_api_keys()
    if not keys:
        return None, "no API key found (set GEMINI_API_KEY or create .apikeys)", None

    # Map model name to URL
    model_urls = {
        "3.5-flash": "https://generativelanguage.googleapis.com/v1beta/models/gemini-3.5-flash:generateContent",
        "3-flash": "https://generativelanguage.googleapis.com/v1beta/models/gemini-3-flash-preview:generateContent",
        "3.1-flash-lite": "https://generativelanguage.googleapis.com/v1beta/models/gemini-3.1-flash-lite:generateContent",
    }

    api_url = model_urls.get(model, model_urls["3.1-flash-lite"])

    prompt = build_prompt(user_message, context)
    payload = json.dumps({
        "contents": [
            {"parts": [{"text": prompt}]}
        ]
    }).encode("utf-8")

    username = context.get("username") if context else None
    selected_index = apikey_settings.get_selected_key(username) if username else None

    if selected_index is not None:
        selected_label = f"KEY{selected_index}"
        locked_order = [pair for pair in keys if pair[0] == selected_label]
        if locked_order:
            # Locked slot is a valid Gemini key -- use it exclusively
            order = locked_order
        else:
            # Locked slot belongs to another provider (Groq/OpenRouter) -- ignore it here
            order = keys[:]
            random.shuffle(order)
    else:
        order = keys[:]
        random.shuffle(order)

    attempts = []
    last_error = "all configured API keys failed"

    for label, api_key in order:
        attempts.append(label)

        req = urllib.request.Request(
            api_url,
            data=payload,
            method="POST",
            headers={
                "Content-Type": "application/json",
                "x-goog-api-key": api_key,
            },
        )

        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                data = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", "ignore")[:200]
            last_error = f"Gemini API error {e.code} ({label}): {body}"
            continue
        except urllib.error.URLError as e:
            last_error = f"network error ({label}): {e.reason}"
            continue
        except Exception as e:
            last_error = f"unexpected error ({label}): {e}"
            continue

        try:
            candidates = data.get("candidates", [])
            if not candidates:
                last_error = f"empty response from Gemini ({label})"
                continue
            parts = candidates[0]["content"]["parts"]
            text = "".join(p.get("text", "") for p in parts).strip()
            if not text:
                last_error = f"empty response from Gemini ({label})"
                continue
        except (KeyError, IndexError, TypeError):
            last_error = f"unexpected response shape from Gemini ({label})"
            continue

        # Success
        debug_info = {
            "used_label": label,
            "used_key_masked": _mask_key(api_key),
            "attempts": attempts,
        }
        return text, None, debug_info

    # Every key failed
    debug_info = {
        "used_label": None,
        "used_key_masked": None,
        "attempts": attempts,
    }
    return None, last_error, debug_info
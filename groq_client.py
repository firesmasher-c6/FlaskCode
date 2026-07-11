import json
import time
import urllib.request
import urllib.error

import apikey_settings
from gemini_client import build_prompt

GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
GROQ_MODELS_URL = "https://api.groq.com/openai/v1/models"
DEFAULT_MODEL = "llama-3.3-70b-versatile"


def _mask_key(key: str) -> str:
    if not key:
        return "(none)"
    if len(key) <= 10:
        return key[:2] + "…" + key[-2:]
    return key[:6] + "…" + key[-4:]


def has_api_key(username: str = None):
    if not username:
        return False
    return apikey_settings.get_groq_key(username) is not None


def key_status_label(username: str = None):
    return "using Groq" if has_api_key(username) else None


def ask(user_message: str, context: dict, model: str = None, timeout: int = 200):
    """
    Returns (answer_text, error_message, debug_info). Exactly one of
    answer_text/error_message will be None. Uses this user's saved Groq
    key (set via /apikey <key> while on a Groq model) -- no fallback,
    Groq has exactly one key slot per user.
    """
    username = context.get("username") if context else None
    api_key = apikey_settings.get_groq_key(username) if username else None
    if not api_key:
        return None, "no Groq key saved -- use /apikey <key> while on a Groq model", None

    prompt = build_prompt(user_message, context)
    payload = json.dumps({
        "model": model or DEFAULT_MODEL,
        "messages": [{"role": "user", "content": prompt}],
    }).encode("utf-8")

    req = urllib.request.Request(
        GROQ_URL,
        data=payload,
        method="POST",
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
            "User-Agent": "FlaskCode/1.0 (python-urllib)",
        },
    )

    debug_info = {"used_label": None, "used_key_masked": _mask_key(api_key), "attempts": ["Groq"]}

    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", "ignore")[:200]
        return None, f"Groq API error {e.code}: {body}", debug_info
    except urllib.error.URLError as e:
        return None, f"network error: {e.reason}", debug_info
    except Exception as e:
        return None, f"unexpected error: {e}", debug_info

    try:
        text = (data["choices"][0]["message"]["content"] or "").strip()
        if not text:
            return None, "empty response from Groq", debug_info
    except (KeyError, IndexError, TypeError):
        return None, "unexpected response shape from Groq", debug_info

    debug_info["used_label"] = "Groq"
    return text, None, debug_info


def ping(timeout: int = 5, username: str = None):
    """Check whether Groq is reachable with this user's saved key, without spending a prompt."""
    api_key = apikey_settings.get_groq_key(username) if username else None
    if not api_key:
        return False, "no Groq key saved for this user"

    req = urllib.request.Request(
        GROQ_MODELS_URL,
        method="GET",
        headers={"Authorization": f"Bearer {api_key}", "User-Agent": "FlaskCode/1.0 (python-urllib)"},
    )

    start = time.time()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            resp.read(1)
            status = resp.status
    except urllib.error.HTTPError as e:
        elapsed = time.time() - start
        if e.code in (401, 403):
            return False, f"reachable but API key rejected ({e.code}) in {elapsed:.2f}s"
        return False, f"HTTP error {e.code} in {elapsed:.2f}s"
    except urllib.error.URLError as e:
        return False, f"unreachable: {e.reason}"
    except Exception as e:
        return False, f"unexpected error: {e}"

    elapsed = time.time() - start
    return True, f"reachable ({status}) in {elapsed:.2f}s"
import json
import time
import urllib.request
import urllib.error

import apikey_settings
from gemini_client import build_prompt

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
OPENROUTER_MODELS_URL = "https://openrouter.ai/api/v1/models"
DEFAULT_MODEL = "openai/gpt-oss-20b:free"

EXTRA_HEADERS = {
    "HTTP-Referer": "https://flaskcode.local",
    "X-Title": "Flask Code",
}


def _mask_key(key: str) -> str:
    if not key:
        return "(none)"
    if len(key) <= 10:
        return key[:2] + "…" + key[-2:]
    return key[:6] + "…" + key[-4:]


def _resolve_key(username: str = None) -> str:
    """
    Return the OpenRouter API key for this user. Priority:
      1. Dedicated openrouter_key saved in .apikeyml (set via /apikey <key> on openrouter model)
      2. The user's selected_key slot from .apikeyml, read from .apikeys
      3. .apikeys slot 3 directly (OpenRouter's fixed slot in the shared file)
    """
    # 1. Explicit openrouter key saved in .apikeyml
    if username:
        key = apikey_settings.get_openrouter_key(username)
        if key:
            return key

        # 2. User locked a slot via /apikey <1|2|3> -- read that slot from .apikeys
        selected = apikey_settings.get_selected_key(username)
        if selected is not None:
            key = apikey_settings.get_key_from_apikeys_slot(selected)
            if key:
                return key

    # 3. Fall back to slot 3 (OpenRouter's default slot in .apikeys)
    return apikey_settings.get_key_from_apikeys_slot(3)


def has_api_key(username: str = None):
    return _resolve_key(username) is not None


def key_status_label(username: str = None):
    return "using OpenRouter" if has_api_key(username) else None


def ask(user_message: str, context: dict, model: str = None, timeout: int = 200):
    """
    Returns (answer_text, error_message, debug_info). Exactly one of
    answer_text/error_message will be None. Resolves the OpenRouter key via
    _resolve_key(): dedicated .apikeyml key, then selected slot from
    .apikeys, then .apikeys slot 3 as default.
    """
    username = context.get("username") if context else None
    api_key = _resolve_key(username)
    if not api_key:
        return None, "no OpenRouter key found -- add it to .apikeys slot 3 or use /apikey <key>", None

    prompt = build_prompt(user_message, context)
    payload = json.dumps({
        "model": model or DEFAULT_MODEL,
        "messages": [{"role": "user", "content": prompt}],
    }).encode("utf-8")

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
    }
    headers.update(EXTRA_HEADERS)

    req = urllib.request.Request(OPENROUTER_URL, data=payload, method="POST", headers=headers)

    debug_info = {"used_label": None, "used_key_masked": _mask_key(api_key), "attempts": ["OpenRouter"]}

    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", "ignore")[:200]
        return None, f"OpenRouter API error {e.code}: {body}", debug_info
    except urllib.error.URLError as e:
        return None, f"network error: {e.reason}", debug_info
    except Exception as e:
        return None, f"unexpected error: {e}", debug_info

    try:
        text = (data["choices"][0]["message"]["content"] or "").strip()
        if not text:
            return None, "empty response from OpenRouter", debug_info
    except (KeyError, IndexError, TypeError):
        return None, "unexpected response shape from OpenRouter", debug_info

    debug_info["used_label"] = "OpenRouter"
    return text, None, debug_info


def ping(timeout: int = 5, username: str = None):
    """Check whether OpenRouter is reachable with this user's resolved key, without spending a prompt."""
    api_key = _resolve_key(username)
    if not api_key:
        return False, "no OpenRouter key found -- add it to .apikeys slot 3 or use /apikey <key>"

    req = urllib.request.Request(
        OPENROUTER_MODELS_URL,
        method="GET",
        headers={"Authorization": f"Bearer {api_key}"},
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
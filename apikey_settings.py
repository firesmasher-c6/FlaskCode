import os
import re
import yaml

SETTINGS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".flask", "user-settings")
APIKEYS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".apikeys")

VALID_KEY_INDEXES = (1, 2, 3)
VALID_PROVIDERS = ("gemini", "openrouter", "groq")
DEFAULT_PROVIDER = "gemini"

# ---------------------------------------------------------------------------
# .apikeyml format (YAML, one file per user: .flask/user-settings/<user>.apikeyml)
#
#   selected_key: 2                 # Gemini slot locked in via /apikey <1|2|3>
#   openrouter_key: "sk-or-v1-..."  # saved via .sw-oprt <key>
#   groq_key: "gsk_..."             # saved via .sw-groq <key>
#   active_provider: groq           # which provider ask() should use for this user
#
# Any of these fields can be present or absent independently -- reads/writes
# always go through _load_data()/_save_data() so setting one field never
# clobbers the others already saved to disk.
# ---------------------------------------------------------------------------


def _file_for(username: str) -> str:
    return os.path.join(SETTINGS_DIR, f"{username.lower()}.apikeyml")


def _load_data(username: str) -> dict:
    """Load this user's full settings dict from their .apikeyml file.
    Returns {} if the user has nothing saved yet or the file is unreadable."""
    if not username:
        return {}

    path = _file_for(username)
    if not os.path.exists(path):
        return {}

    try:
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _save_data(username: str, data: dict):
    """Write this user's full settings dict back to .apikeyml. Returns (success, message)."""
    if not username:
        return False, "No user is logged in"

    os.makedirs(SETTINGS_DIR, exist_ok=True)
    try:
        with open(_file_for(username), "w", encoding="utf-8") as f:
            yaml.dump(data, f, default_flow_style=False)
        return True, "saved"
    except Exception as e:
        return False, f"Failed to save apikey settings: {e}"


def get_selected_key(username: str):
    """
    Return the Gemini apikey slot (1, 2, or 3) this user has permanently
    locked in via /apikey, or None if they haven't picked one (falls back
    to the normal random selection in gemini_client.ask).
    """
    index = _load_data(username).get("selected_key")
    return index if index in VALID_KEY_INDEXES else None


def set_selected_key(username: str, index: int):
    """
    Persist this user's chosen Gemini apikey slot to
    .flask/user-settings/<user>.apikeyml (YAML), leaving any saved
    openrouter_key / groq_key / active_provider untouched.
    Returns (success, message).
    """
    if not username:
        return False, "No user is logged in"
    if index not in VALID_KEY_INDEXES:
        return False, "apikey slot must be 1, 2, or 3"

    data = _load_data(username)
    data["selected_key"] = index

    success, msg = _save_data(username, data)
    if success:
        return True, f"KEY{index} is now permanently used for your requests (no fallback if it fails)"
    return False, msg


def get_openrouter_key(username: str):
    """Return this user's saved OpenRouter API key, or None if they haven't set one."""
    key = _load_data(username).get("openrouter_key")
    return key.strip() if isinstance(key, str) and key.strip() else None


def set_openrouter_key(username: str, api_key: str):
    """
    Persist this user's OpenRouter API key and switch their active provider
    to OpenRouter (used by the .sw-oprt <apikey> secret command).
    Returns (success, message).
    """
    if not username:
        return False, "No user is logged in"
    if not api_key or not api_key.strip():
        return False, "No API key given"

    data = _load_data(username)
    data["openrouter_key"] = api_key.strip()
    data["active_provider"] = "openrouter"

    success, msg = _save_data(username, data)
    if success:
        return True, "Switched to OpenRouter (openai/gpt-oss-20b:free) -- key saved"
    return False, msg


def get_groq_key(username: str):
    """Return this user's saved Groq API key, or None if they haven't set one."""
    key = _load_data(username).get("groq_key")
    return key.strip() if isinstance(key, str) and key.strip() else None


def set_groq_key(username: str, api_key: str):
    """
    Persist this user's Groq API key and switch their active provider to
    Groq (used by the .sw-groq <apikey> secret command).
    Returns (success, message).
    """
    if not username:
        return False, "No user is logged in"
    if not api_key or not api_key.strip():
        return False, "No API key given"

    data = _load_data(username)
    data["groq_key"] = api_key.strip()
    data["active_provider"] = "groq"

    success, msg = _save_data(username, data)
    if success:
        return True, "Switched to Groq (llama-3.3-70b-versatile) -- key saved"
    return False, msg


def get_active_provider(username: str) -> str:
    """
    Return this user's active AI provider: 'gemini' (the default, including
    for logged-out/unknown users), 'openrouter', or 'groq'.
    """
    provider = _load_data(username).get("active_provider")
    return provider if provider in VALID_PROVIDERS else DEFAULT_PROVIDER


def get_key_from_apikeys_slot(slot: int) -> str:
    """
    Read a raw key directly from .apikeys by slot number (1, 2, or 3).
    Strips -! comment lines before parsing. Returns the key string or None.
    Used by groq_client / openrouter_client to pull their keys from the
    shared .apikeys file instead of requiring a separate /apikey <key> paste.
    """
    if slot not in VALID_KEY_INDEXES:
        return None
    if not os.path.exists(APIKEYS_FILE):
        return None
    try:
        with open(APIKEYS_FILE, "r", encoding="utf-8") as f:
            raw = f.read()
        # Strip custom -! comment lines (same as gemini_client does)
        raw = re.sub(r'-!.*$', '', raw, flags=re.MULTILINE)
        data = yaml.safe_load(raw)
        if not isinstance(data, dict):
            return None
        value = data.get(f"key_{slot}")
        if not value or not isinstance(value, str):
            return None
        value = value.strip()
        return value if value and value.upper() != "YOUR_API_KEY_HERE" else None
    except Exception:
        return None


def set_active_provider(username: str, provider: str):
    """
    Explicitly switch this user's active provider without touching any
    saved keys (used by .sw-gem to switch back to Gemini after trying
    OpenRouter/Groq). Returns (success, message).
    """
    if not username:
        return False, "No user is logged in"
    if provider not in VALID_PROVIDERS:
        return False, f"Unknown provider '{provider}' -- must be one of: {', '.join(VALID_PROVIDERS)}"

    data = _load_data(username)
    data["active_provider"] = provider

    success, msg = _save_data(username, data)
    if success:
        return True, f"Switched to {provider.capitalize()}"
    return False, msg
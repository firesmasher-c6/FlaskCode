import os
import json
from datetime import datetime

SAVED_INFO_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "saved-info")

MAX_NOTES_IN_PROMPT = 20  # cap how many notes get sent to the AI per message


def _ensure_dir():
    os.makedirs(SAVED_INFO_DIR, exist_ok=True)


def _file_for(username: str) -> str:
    return os.path.join(SAVED_INFO_DIR, f"{username.lower()}.json")


def load_info(username: str) -> dict:
    """Load saved-info/<user>.json. Always returns a dict with a 'notes' list."""
    path = _file_for(username)
    if not os.path.exists(path):
        return {"username": username, "notes": []}
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            return {"username": username, "notes": []}
        data.setdefault("notes", [])
        return data
    except Exception:
        return {"username": username, "notes": []}


def save_info(username: str, data: dict):
    """Write the given data dict to saved-info/<user>.json. Returns (success, message)."""
    _ensure_dir()
    path = _file_for(username)
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        return True, "saved"
    except Exception as e:
        return False, f"Failed to save: {e}"


def remember(username: str, text: str):
    """Add a new fact/note the AI should remember about this user. Returns (success, message)."""
    if not text or not text.strip():
        return False, "Nothing to remember"

    data = load_info(username)
    data["username"] = username
    data["notes"].append({
        "text": text.strip(),
        "added": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    })

    success, msg = save_info(username, data)
    if success:
        return True, f"Remembered ({len(data['notes'])} total note(s))"
    return False, msg


def forget(username: str, index: int):
    """Remove note #index (1-based, as shown by list_notes). Returns (success, message)."""
    data = load_info(username)
    notes = data["notes"]

    if index < 1 or index > len(notes):
        count = len(notes)
        return False, f"No note #{index} (you have {count} saved)"

    removed = notes.pop(index - 1)
    data["notes"] = notes

    success, msg = save_info(username, data)
    if success:
        return True, f'Forgot: "{removed["text"]}"'
    return False, msg


def forget_all(username: str):
    """Wipe all saved info for this user. Returns (success, message)."""
    success, msg = save_info(username, {"username": username, "notes": []})
    if success:
        return True, "Cleared all saved info"
    return False, msg


def list_notes(username: str) -> list:
    """Return the raw list of note dicts ({'text', 'added'}) for this user."""
    return load_info(username)["notes"]


def format_for_ai(username: str) -> str:
    """Read saved-info/<user>.json, parse it, and build a context block for the AI prompt."""
    data = load_info(username)
    notes = data.get("notes", [])
    if not notes:
        return ""

    recent = notes[-MAX_NOTES_IN_PROMPT:]
    lines = [f"Saved info about {username} (parsed from saved-info/{username.lower()}.json):"]
    for n in recent:
        text = n.get("text", "")
        added = n.get("added")
        lines.append(f"  - [{added}] {text}" if added else f"  - {text}")

    return "\n".join(lines)
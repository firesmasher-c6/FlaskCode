import os
import yaml
import random
import json
from datetime import datetime

CHATS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "chats")
PINS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "users.pins")


def _ensure_chats_dir():
    """Create chats directory if it doesn't exist."""
    os.makedirs(CHATS_DIR, exist_ok=True)


def _load_pins() -> dict:
    """Load PIN mapping from users.pins file. Format: username:pin"""
    if not os.path.exists(PINS_FILE):
        return {}
    
    pins = {}
    try:
        with open(PINS_FILE, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("-!"):
                    continue
                if ":" in line:
                    name, pin = line.split(":", 1)
                    pins[name.lower()] = pin
    except Exception:
        pass
    return pins


def _save_pins(pins: dict):
    """Save PIN mapping to users.pins file."""
    try:
        with open(PINS_FILE, "w", encoding="utf-8") as f:
            for name, pin in pins.items():
                f.write(f"{name}:{pin}\n")
    except Exception as e:
        raise RuntimeError(f"Failed to save PINs: {e}")


def generate_pin(username: str) -> str:
    """Generate or retrieve a 4-digit PIN for a user."""
    pins = _load_pins()
    username_lower = username.lower()
    
    if username_lower in pins:
        return pins[username_lower]
    
    # Generate new 4-digit PIN
    new_pin = f"{random.randint(1000, 9999)}"
    pins[username_lower] = new_pin
    _save_pins(pins)
    return new_pin


def save_chat(username: str, messages: list) -> tuple:
    """
    Save chat history for a user.
    messages: list of dicts with {'role': 'user'|'flask', 'text': '...', 'timestamp': '...'}
    Returns (success: bool, message: str, pin: str)
    """
    _ensure_chats_dir()
    username_lower = username.lower()
    
    pin = generate_pin(username)
    chat_file = os.path.join(CHATS_DIR, f"{username_lower}.yml")
    
    try:
        chat_data = {
            "username": username,
            "pin": pin,
            "created": datetime.now().isoformat(),
            "messages": messages,
        }
        
        with open(chat_file, "w", encoding="utf-8") as f:
            yaml.dump(chat_data, f, default_flow_style=False, allow_unicode=True)
        
        return True, f"Chat saved (PIN: {pin})", pin
    except Exception as e:
        return False, f"Failed to save chat: {e}", pin


def load_chat(username: str, pin: str) -> tuple:
    """
    Load chat history for a user by PIN.
    Returns (success: bool, messages: list|None, message: str)
    """
    _ensure_chats_dir()
    username_lower = username.lower()
    chat_file = os.path.join(CHATS_DIR, f"{username_lower}.yml")
    
    if not os.path.exists(chat_file):
        return False, None, "No chat history found"
    
    try:
        with open(chat_file, "r", encoding="utf-8") as f:
            chat_data = yaml.safe_load(f)
        
        if not chat_data:
            return False, None, "Chat file is empty"
        
        # Verify PIN
        stored_pin = chat_data.get("pin")
        if stored_pin != pin:
            return False, None, "Incorrect PIN"
        
        messages = chat_data.get("messages", [])
        created = chat_data.get("created", "unknown")
        
        return True, messages, f"Chat loaded (created: {created})"
    except Exception as e:
        return False, None, f"Failed to load chat: {e}"


def get_user_pin(username: str) -> str:
    """Get the PIN for a user (returns existing or generates new)."""
    return generate_pin(username)


def find_user_by_pin(pin: str):
    """Look up which user a PIN belongs to. Returns the username (lowercase) or None."""
    if not pin:
        return None
    pins = _load_pins()
    for username, stored_pin in pins.items():
        if stored_pin == pin:
            return username
    return None


def list_chats() -> list:
    """List all saved chats."""
    _ensure_chats_dir()
    chats = []
    try:
        for filename in os.listdir(CHATS_DIR):
            if filename.endswith(".yml"):
                filepath = os.path.join(CHATS_DIR, filename)
                try:
                    with open(filepath, "r", encoding="utf-8") as f:
                        data = yaml.safe_load(f)
                        if data:
                            chats.append({
                                "username": data.get("username"),
                                "pin": data.get("pin"),
                                "created": data.get("created"),
                            })
                except:
                    pass
    except:
        pass
    return chats
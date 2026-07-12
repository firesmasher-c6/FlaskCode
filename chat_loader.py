import os
import yaml

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CHATS_DIR = os.path.join(BASE_DIR, "chats")


def load_chat_history(username):
    """Load chat history for a user from chats/{username}.yml"""
    chat_file = os.path.join(CHATS_DIR, f"{username.lower()}.yml")
    if not os.path.exists(chat_file):
        return []
    try:
        with open(chat_file, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f)
        if not data:
            return []
        return data.get('messages', [])
    except Exception:
        return []


def save_chat_history(username, messages):
    if not username or not messages:
        return False
    try:
        os.makedirs(CHATS_DIR, exist_ok=True)
        chat_file = os.path.join(CHATS_DIR, f"{username.lower()}.yml")
        chat_data = {'username': username, 'messages': messages}
        with open(chat_file, 'w', encoding='utf-8') as f:
            yaml.dump(chat_data, f, default_flow_style=False, allow_unicode=True)
        return True
    except Exception:
        return False


def format_history_for_ai(messages):
    if not messages:
        return ""
    history = "Previous conversation history:\n"
    for msg in messages[-10:]:
        role = msg.get('role', 'unknown')
        text = msg.get('text', '')
        if role == 'user':
            history += f"User: {text}\n"
        elif role == 'flask':
            history += f"Flask: {text}\n"
    return history + "\n"

import os
import yaml

# Windows path where the project lives
PROJECT_DIR = r'C:\Users\Admin\OneDrive\Documents\PortfolioWebsite\AI'
CHATS_DIR = os.path.join(PROJECT_DIR, 'chats')

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
        
        messages = data.get('messages', [])
        return messages
    except Exception as e:
        print(f"Error loading chat history: {e}")
        return []

def save_chat_history(username, messages):
    """Save chat history for a user to chats/{username}.yml"""
    if not username or not messages:
        return False
    
    try:
        os.makedirs(CHATS_DIR, exist_ok=True)
        
        chat_file = os.path.join(CHATS_DIR, f"{username.lower()}.yml")
        
        chat_data = {
            'username': username,
            'messages': messages
        }
        
        with open(chat_file, 'w', encoding='utf-8') as f:
            yaml.dump(chat_data, f, default_flow_style=False, allow_unicode=True)
        
        return True
    except Exception as e:
        print(f"Error saving chat history: {e}")
        return False

def format_history_for_ai(messages):
    """Format chat history for sending to AI context."""
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
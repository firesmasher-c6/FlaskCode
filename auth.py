import os
import hashlib
import re

USERS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "users.env")


def _hash_password(password: str) -> str:
    """Hash password using SHA-256."""
    return hashlib.sha256(password.encode()).hexdigest()


def _load_users() -> dict:
    """Load users from users.env file. Format: username:hashed_password"""
    if not os.path.exists(USERS_FILE):
        return {}
    
    users = {}
    try:
        with open(USERS_FILE, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("-!"):
                    continue
                if ":" in line:
                    name, hashed_pw = line.split(":", 1)
                    users[name.lower()] = hashed_pw
    except Exception:
        pass
    return users


def _save_users(users: dict):
    """Save users to users.env file."""
    try:
        with open(USERS_FILE, "w", encoding="utf-8") as f:
            for name, hashed_pw in users.items():
                f.write(f"{name}:{hashed_pw}\n")
    except Exception as e:
        raise RuntimeError(f"Failed to save users: {e}")


def register(username: str, password: str) -> tuple:
    """
    Register a new user.
    Returns (success: bool, message: str)
    """
    if not username or not password:
        return False, "Username and password cannot be empty"
    
    if not re.match(r'^[a-zA-Z0-9_-]{3,20}$', username):
        return False, "Username must be 3-20 characters (alphanumeric, dash, underscore only)"
    
    if len(password) < 6:
        return False, "Password must be at least 6 characters"
    
    users = _load_users()
    username_lower = username.lower()
    
    if username_lower in users:
        return False, "Username already exists"
    
    hashed = _hash_password(password)
    users[username_lower] = hashed
    
    try:
        _save_users(users)
        return True, f"User '{username}' registered successfully"
    except Exception as e:
        return False, str(e)


def login(username: str, password: str) -> tuple:
    """
    Authenticate a user.
    Returns (success: bool, message: str)
    """
    if not username or not password:
        return False, "Username and password cannot be empty"
    
    users = _load_users()
    username_lower = username.lower()
    
    if username_lower not in users:
        return False, "Username or password incorrect"
    
    hashed = _hash_password(password)
    if users[username_lower] == hashed:
        return True, f"Welcome back, {username}!"
    
    return False, "Username or password incorrect"


def change_password(username: str, current_password: str, new_password: str) -> tuple:
    """
    Change password for an authenticated user.
    Returns (success: bool, message: str)
    """
    if not username or not current_password or not new_password:
        return False, "All fields are required"
    
    if len(new_password) < 6:
        return False, "New password must be at least 6 characters"
    
    users = _load_users()
    username_lower = username.lower()
    
    if username_lower not in users:
        return False, "User not found"
    
    current_hashed = _hash_password(current_password)
    if users[username_lower] != current_hashed:
        return False, "Current password is incorrect"
    
    new_hashed = _hash_password(new_password)
    users[username_lower] = new_hashed
    
    try:
        _save_users(users)
        return True, "Password changed successfully"
    except Exception as e:
        return False, str(e)
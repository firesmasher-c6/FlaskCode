"""
server_config.py  —  FlaskCode-Server configuration loader
===========================================================
Reads {DIR}/.conf/server_config and returns parsed settings.
Called once at server startup.

server_config format:
    # comment lines (ignored)
    ?password:000000         # server connection password (max 10 chars)
    ?True:true               # whether to encrypt connections
    ?EncryptionMethod:SHA256 # SHA256 | SHA1 | BASE64
"""

import os
import hashlib
import base64

_CONFIG_FILENAME = "server_config"
_CONFIG_TEMPLATE = """\
# SERVER PASSWORD. SHARE PRIVATELY!

# Password max characters: 10
?password:000000

# Encrypt connection? 
?True:true
# Valid Encryption: SHA256, SHA1, BASE64
?EncryptionMethod:SHA256

# FlaskCode Server (Linux)
# MIT, No Rights Reserved.
"""

VALID_ENCRYPTION_METHODS = ("SHA256", "SHA1", "BASE64")


def _config_path(server_dir: str) -> str:
    return os.path.join(server_dir, ".conf", _CONFIG_FILENAME)


def _ensure_config(server_dir: str) -> str:
    """Create the default config file if it doesn't exist. Returns the path."""
    path = _config_path(server_dir)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    if not os.path.exists(path):
        with open(path, "w") as f:
            f.write(_CONFIG_TEMPLATE)
        print(f"[config] Created default config at {path}")
    return path


def load(server_dir: str | None = None) -> dict:
    """
    Load and parse server_config. Returns a dict:
        {
            "password":          str,   # raw password string
            "encrypt":           bool,
            "encryption_method": str,   # "SHA256" | "SHA1" | "BASE64"
        }
    Falls back to safe defaults if the file is missing or unparseable.
    """
    if server_dir is None:
        server_dir = os.path.dirname(os.path.abspath(__file__))

    path = _ensure_config(server_dir)

    defaults = {
        "password": "000000",
        "encrypt": True,
        "encryption_method": "SHA256",
    }

    try:
        with open(path) as f:
            lines = f.readlines()
    except OSError as e:
        print(f"[config] Warning: could not read config ({e}) — using defaults")
        return defaults

    result = dict(defaults)

    for raw in lines:
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if not line.startswith("?"):
            continue

        # strip leading '?'
        line = line[1:]
        if ":" not in line:
            continue

        key, _, value = line.partition(":")
        key = key.strip()
        value = value.strip()

        if key == "password":
            pw = value[:10]  # enforce max 10 chars
            if pw != value:
                print("[config] Warning: password truncated to 10 characters")
            result["password"] = pw

        elif key == "True":
            result["encrypt"] = value.lower() in ("true", "1", "yes")

        elif key == "EncryptionMethod":
            method = value.upper()
            if method in VALID_ENCRYPTION_METHODS:
                result["encryption_method"] = method
            else:
                print(f"[config] Warning: unknown EncryptionMethod '{value}' — using SHA256")
                result["encryption_method"] = "SHA256"

    return result


def hash_password(password: str, method: str) -> str:
    """
    Hash a password using the configured method.
    Used both server-side (to store the expected token) and
    client-side (to produce the token to send).
    """
    method = method.upper()
    encoded = password.encode("utf-8")
    if method == "SHA256":
        return hashlib.sha256(encoded).hexdigest()
    elif method == "SHA1":
        return hashlib.sha1(encoded).hexdigest()
    elif method == "BASE64":
        return base64.b64encode(encoded).decode("ascii")
    else:
        # fallback
        return hashlib.sha256(encoded).hexdigest()


def verify_token(provided_token: str, config: dict) -> bool:
    """
    Return True if the provided token matches the configured password
    under the configured encryption method (or plain if encrypt=False).
    """
    password = config["password"]
    if not password or password == "000000":
        # No real password set — allow all
        return True
    if config["encrypt"]:
        expected = hash_password(password, config["encryption_method"])
    else:
        expected = password
    return provided_token == expected

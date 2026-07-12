#!/usr/bin/env python3
"""
flaskcc  —  FlaskCode Client
=============================
A feature-complete terminal client for FlaskCode-Server.

Usage:
    python flaskcc.py HOST@PORT [--pass PASSWORD] [--user USERNAME]

All server endpoints are accessible from the interactive shell.
Type  help  for the full command list.
"""

# ── stdlib ─────────────────────────────────────────────────────────────────
import argparse
import base64
import getpass
import hashlib
import json
import os
import shutil
import sys
import textwrap
import time
import urllib.error
import urllib.request

# ── ANSI colours ────────────────────────────────────────────────────────────

_NO_COLOR = not sys.stdout.isatty() or os.environ.get("NO_COLOR")

def _c(code: str, text: str) -> str:
    return text if _NO_COLOR else f"\033[{code}m{text}\033[0m"

def bold(t):    return _c("1",    t)
def dim(t):     return _c("2",    t)
def cyan(t):    return _c("96",   t)
def magenta(t): return _c("95",   t)
def green(t):   return _c("92",   t)
def yellow(t):  return _c("93",   t)
def red(t):     return _c("91",   t)
def blue(t):    return _c("94",   t)
def gray(t):    return _c("90",   t)

# ── terminal width ──────────────────────────────────────────────────────────

def _tw() -> int:
    return shutil.get_terminal_size((80, 24)).columns

def separator(char="─"):
    return cyan(bold(char * min(_tw(), 72)))

# ── banner ──────────────────────────────────────────────────────────────────

BANNER = f"""
{cyan(bold('╔══════════════════════════════════════════════════════════╗'))}
{cyan(bold('║'))}  {magenta(bold('F L A S K   C O D E  —  C L I  C L I E N T'))}             {cyan(bold('║'))}
{cyan(bold('║'))}  {blue(bold('>> Connect  ·  Chat  ·  Code  ·  Files <<'))}              {cyan(bold('║'))}
{cyan(bold('╚══════════════════════════════════════════════════════════╝'))}
{dim('Type')} {green(bold('help'))} {dim('to see all commands.')}
"""

HELP_TEXT = f"""
{cyan(bold('━━━  AUTH  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━'))}
  {green(bold('register'))} <user> <pass>     Create a new account
  {green(bold('login'))} <user> <pass>        Log in (or {green(bold('login'))} for prompt)
  {green(bold('login-pin'))} <pin>            Log in with a saved PIN
  {green(bold('logout'))}                     Save chat and log out
  {green(bold('passwd'))} <old> <new>         Change your password
  {green(bold('whoami'))}                     Show your username + PIN

{cyan(bold('━━━  CHAT  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━'))}
  {green(bold('<message>'))}                  Send a message (default action)
  {green(bold('model'))} [name]               Show or switch the active model
  {green(bold('models'))}                     List all available models
  {green(bold('history'))}                    Print your chat history
  {green(bold('load'))} <pin>                 Load a saved chat by PIN
  {green(bold('clear'))}                      Clear your chat history
  {green(bold('export'))}                     Export chat to a .txt file

{cyan(bold('━━━  KNOWLEDGE  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━'))}
  {green(bold('learn'))} <sentence>           Teach the knowledge engine
  {green(bold('reset-knowledge'))}            Wipe + reseed knowledge base

{cyan(bold('━━━  FILES  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━'))}
  {green(bold('files'))}                      List files on server
  {green(bold('read'))} <filename>            Read a file (by name)
  {green(bold('readpath'))} <path>            Read a file (by absolute path)
  {green(bold('write'))} <filename>           Write/create a file (editor prompt)
  {green(bold('write'))} <filename> <content> Write inline content
  {green(bold('save-block'))}                 Interactively save a code block
  {green(bold('clear-outputs'))}              Wipe the server outputs/ folder

{cyan(bold('━━━  REMEMBER  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━'))}
  {green(bold('remember'))} <text>            Save a note to your profile
  {green(bold('notes'))}                      List all your saved notes
  {green(bold('forget'))} <index>             Delete a note by index
  {green(bold('forget-all'))}                 Delete all your notes

{cyan(bold('━━━  API KEYS  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━'))}
  {green(bold('apikey-slot'))} <1|2|3>        Select Gemini API key slot
  {green(bold('apikey-groq'))} <key>          Set your Groq API key
  {green(bold('apikey-openrouter'))} <key>    Set your OpenRouter API key

{cyan(bold('━━━  SERVER / DEBUG  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━'))}
  {green(bold('ping'))}                       Ping server (tests AI client)
  {green(bold('health'))}                     Server health + knowledge stats
  {green(bold('stats'))}                      Your stats (model, API key status)
  {green(bold('clock'))}                      Ask server for the current time
  {green(bold('debug on/off'))}               Toggle server debug output
  {green(bold('debug'))}                      Toggle debug output in responses

{cyan(bold('━━━  SESSION  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━'))}
  {green(bold('help'))}                       Show this menu
  {green(bold('exit'))} / {green(bold('quit'))}              Logout and exit
"""

# ── HTTP helpers ─────────────────────────────────────────────────────────────

class APIError(Exception):
    pass

class FlaskCodeClient:
    """Thin HTTP wrapper around the FlaskCode-Server REST API."""

    def __init__(self, base_url: str, token: str = ""):
        self.base_url = base_url.rstrip("/")
        self.token = token

    def _headers(self) -> dict:
        h = {"Content-Type": "application/json"}
        if self.token:
            h["X-FlaskCode-Token"] = self.token
        return h

    def _request(self, method: str, path: str, data: dict | None = None,
                 params: dict | None = None) -> dict:
        url = self.base_url + path
        if params:
            qs = "&".join(f"{k}={urllib.parse.quote(str(v))}" for k, v in params.items())
            url = f"{url}?{qs}"

        body = json.dumps(data).encode() if data is not None else None
        req = urllib.request.Request(url, data=body, method=method,
                                     headers=self._headers())
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                return json.loads(resp.read())
        except urllib.error.HTTPError as e:
            raw = e.read()
            try:
                return json.loads(raw)
            except Exception:
                raise APIError(f"HTTP {e.code}: {raw.decode(errors='replace')}")
        except urllib.error.URLError as e:
            raise APIError(f"Connection failed: {e.reason}")

    # convenience wrappers
    def get(self, path, params=None):
        return self._request("GET", path, params=params)

    def post(self, path, data=None):
        return self._request("POST", path, data=data or {})

    # ── auth ──────────────────────────────────────────────────────────────
    def register(self, username, password):
        return self.post("/auth/register", {"username": username, "password": password})

    def login(self, username, password):
        return self.post("/auth/login", {"username": username, "password": password})

    def login_pin(self, pin):
        return self.post("/auth/login-pin", {"pin": pin})

    def logout(self, username):
        return self.post("/auth/logout", {"username": username})

    def change_password(self, username, old, new):
        return self.post("/auth/change-password",
                         {"username": username, "current_password": old, "new_password": new})

    # ── me / stats ────────────────────────────────────────────────────────
    def me(self, username):
        return self.get("/me", {"username": username})

    def stats(self, username, model):
        return self.get("/stats", {"username": username, "model": model})

    # ── chat ─────────────────────────────────────────────────────────────
    def chat(self, username, message, model):
        return self.post("/chat", {"username": username, "message": message, "model": model})

    def chat_history(self, username):
        return self.get("/chat/history", {"username": username})

    def chat_load(self, username, pin):
        return self.post("/chat/load", {"username": username, "pin": pin})

    def chat_clear(self, username):
        return self.post("/chat/clear", {"username": username})

    def chat_export(self, username):
        return self.post("/chat/export", {"username": username})

    # ── knowledge ─────────────────────────────────────────────────────────
    def learn(self, username, sentence):
        return self.post("/learn", {"username": username, "sentence": sentence})

    def reset_knowledge(self):
        return self.post("/reset-knowledge")

    # ── files ─────────────────────────────────────────────────────────────
    def files(self):
        return self.get("/files")

    def read_file(self, username, filename):
        return self.post("/files/read", {"username": username, "filename": filename})

    def read_path(self, username, filepath):
        return self.post("/files/read-path", {"username": username, "filepath": filepath})

    def write_file(self, username, filename, content):
        return self.post("/files/write", {"username": username, "filename": filename,
                                           "content": content})

    def save_block(self, language, code, filename):
        return self.post("/files/save-block",
                         {"language": language, "code": code, "filename": filename})

    def clear_outputs(self):
        return self.post("/files/clear-outputs")

    # ── remember ─────────────────────────────────────────────────────────
    def remember(self, username, text):
        return self.post("/remember", {"username": username, "text": text})

    def notes(self, username):
        return self.get("/remember", {"username": username})

    def forget(self, username, index):
        return self.post("/remember/forget", {"username": username, "index": index})

    def forget_all(self, username):
        return self.post("/remember/forget-all", {"username": username})

    # ── apikeys ───────────────────────────────────────────────────────────
    def apikey_slot(self, username, slot):
        return self.post("/apikey/set-slot", {"username": username, "slot": slot})

    def apikey_groq(self, username, key):
        return self.post("/apikey/set-groq", {"username": username, "key": key})

    def apikey_openrouter(self, username, key):
        return self.post("/apikey/set-openrouter", {"username": username, "key": key})

    # ── ping / debug / health ─────────────────────────────────────────────
    def ping(self, username, model):
        return self.post("/ping", {"username": username, "model": model})

    def health(self):
        return self.get("/health")

    def models(self):
        return self.get("/models")

    def clock(self, username, model):
        return self.get("/clock", {"username": username, "model": model})

    def debug_on(self):
        return self.post("/debug/on")

    def debug_off(self):
        return self.post("/debug/off")


# urllib.parse isn't imported yet in the helper — fix that
import urllib.parse  # noqa: E402 (after the class definition)


# ── token derivation (mirrors server_config.py logic) ──────────────────────

def _derive_token(password: str, method: str, encrypt: bool) -> str:
    """
    Produce the token to send in X-FlaskCode-Token.
    Called once during connection setup.
    """
    if not encrypt:
        return password
    m = method.upper()
    enc = password.encode("utf-8")
    if m == "SHA256":
        return hashlib.sha256(enc).hexdigest()
    elif m == "SHA1":
        return hashlib.sha1(enc).hexdigest()
    elif m == "BASE64":
        return base64.b64encode(enc).decode("ascii")
    return hashlib.sha256(enc).hexdigest()


def _negotiate_token(api: FlaskCodeClient, raw_password: str) -> str:
    """
    Ask /health (no auth required) — if it comes back with encryption_method
    we use it. Otherwise we try SHA256 by default.
    The server exposes encryption settings in /health if the admin added it,
    but a vanilla server just returns ok:true; we fall back gracefully.
    """
    try:
        h = api.get("/health")
        method = h.get("encryption_method", "SHA256")
        encrypt = h.get("encrypt", True)
        if isinstance(encrypt, str):
            encrypt = encrypt.lower() != "false"
    except APIError:
        method = "SHA256"
        encrypt = True
    return _derive_token(raw_password, method, encrypt)


# ── output helpers ──────────────────────────────────────────────────────────

def _ok(msg: str):
    print(f"{green(bold('✓'))} {msg}")

def _err(msg: str):
    print(f"{red(bold('✗'))} {msg}")

def _info(msg: str):
    print(f"{blue(bold('·'))} {msg}")

def _warn(msg: str):
    print(f"{yellow(bold('⚠'))} {msg}")

def _print_answer(answer: str):
    """Pretty-print the AI answer with word-wrap and code block highlighting."""
    if not answer:
        return
    width = min(_tw(), 88)
    in_code = False
    print()
    for line in answer.splitlines():
        stripped = line.strip()
        if stripped.startswith("```"):
            in_code = not in_code
            lang = stripped[3:].strip()
            if in_code:
                label = f" {lang} " if lang else " code "
                print(f"  {cyan(bold('┌─' + label + '─' * max(0, 40 - len(label)) + '┐'))}")
            else:
                print(f"  {cyan(bold('└' + '─' * 42 + '┘'))}")
            continue
        if in_code:
            print(f"  {dim('│')} {yellow(line)}")
        else:
            wrapped = textwrap.wrap(line, width - 4) if line.strip() else [""]
            for wl in wrapped:
                print(f"  {wl}")
    print()

def _print_history(messages: list):
    width = min(_tw(), 88)
    for msg in messages:
        role = msg.get("role", "?")
        text = msg.get("text", "")
        ts   = msg.get("timestamp", "")
        if role == "user":
            label = cyan(bold("you"))
        else:
            label = magenta(bold("flask"))
        print(f"\n  {label} {dim(ts)}")
        for line in text.splitlines():
            for wl in (textwrap.wrap(line, width - 6) if line.strip() else [""]):
                print(f"    {wl}")
    print()

def _confirm(prompt: str) -> bool:
    try:
        ans = input(f"{yellow('?')} {prompt} {dim('[y/N]')} ").strip().lower()
        return ans in ("y", "yes")
    except (KeyboardInterrupt, EOFError):
        return False

def _multiline_input(prompt="Content (blank line to finish):") -> str:
    print(dim(prompt))
    lines = []
    while True:
        try:
            line = input()
        except (KeyboardInterrupt, EOFError):
            break
        if line == "":
            break
        lines.append(line)
    return "\n".join(lines)


# ── REPL session ─────────────────────────────────────────────────────────────

class Session:
    def __init__(self, api: FlaskCodeClient):
        self.api = api
        self.username: str | None = None
        self.pin: str | None = None
        self.model: str = "3.1-flash-lite"
        self._debug_local = False   # show debug block in this client

    # ── helpers ──────────────────────────────────────────────────────────

    def _need_login(self) -> bool:
        if not self.username:
            _err("You must be logged in. Use: login <user> <pass>")
            return True
        return False

    def _call(self, fn, *args, **kwargs):
        """Wrap an API call, print errors, return result or None."""
        try:
            return fn(*args, **kwargs)
        except APIError as e:
            _err(str(e))
            return None

    def _handle_chat_response(self, resp: dict):
        if not resp:
            return
        if resp.get("action_log"):
            print(cyan(bold("\n  ── server actions ──")))
            for line in resp["action_log"]:
                print(f"  {dim(line)}")

        answer = resp.get("answer") or ""
        if answer:
            _print_answer(answer)
        elif resp.get("error"):
            _err(resp["error"])

        if resp.get("saved_files"):
            for f in resp["saved_files"]:
                _ok(f"Auto-saved: {bold(f)}")

        plain = resp.get("plain_blocks") or []
        if plain:
            print(cyan(bold(f"\n  {len(plain)} unsaved code block(s):")))
            for i, blk in enumerate(plain, 1):
                lang = blk.get("language", "?")
                preview = (blk.get("code") or "")[:80].replace("\n", " ")
                print(f"  {i}. {yellow(lang)}: {dim(preview)}...")
            if _confirm("Save one of these blocks?"):
                try:
                    idx = int(input(f"  {dim('Block number:')} ")) - 1
                    blk = plain[idx]
                    fname = input(f"  {dim('Filename:')} ").strip()
                    if fname:
                        r = self._call(self.api.save_block,
                                       blk.get("language", "txt"),
                                       blk.get("code", ""), fname)
                        if r and r.get("ok"):
                            _ok(f"Saved: {bold(fname)}")
                        elif r:
                            _err(r.get("error", "save failed"))
                except (ValueError, IndexError):
                    _warn("Invalid selection")

        if self._debug_local and resp.get("debug"):
            dbg = resp["debug"]
            print(gray(f"\n  [debug] {dbg.get('api_key_info','')}"))
            if dbg.get("directives"):
                print(gray(f"  {dbg['directives']}"))

    # ── command handlers ──────────────────────────────────────────────────

    def cmd_register(self, args):
        if len(args) < 2:
            _err("Usage: register <username> <password>"); return
        r = self._call(self.api.register, args[0], args[1])
        if r and r.get("ok"):
            _ok(r.get("message", "Registered"))
            _info(f"Your PIN: {bold(r.get('pin','?'))}")
        elif r:
            _err(r.get("error", "Registration failed"))

    def cmd_login(self, args):
        if len(args) >= 2:
            user, pw = args[0], args[1]
        else:
            user = (args[0] if args else input(f"  {dim('Username:')} ").strip())
            pw   = getpass.getpass(f"  Password: ")
        r = self._call(self.api.login, user, pw)
        if r and r.get("ok"):
            self.username = user
            self.pin      = r.get("pin")
            _ok(f"Logged in as {cyan(bold(user))}  |  PIN: {bold(self.pin)}  |  history: {r.get('history_count',0)} messages")
        elif r:
            _err(r.get("error", "Login failed"))

    def cmd_login_pin(self, args):
        if not args:
            _err("Usage: login-pin <pin>"); return
        r = self._call(self.api.login_pin, args[0])
        if r and r.get("ok"):
            self.username = r.get("username")
            self.pin      = r.get("pin")
            _ok(f"Logged in as {cyan(bold(self.username))}  |  history: {r.get('history_count',0)} messages")
        elif r:
            _err(r.get("error", "PIN login failed"))

    def cmd_logout(self, args):
        if self._need_login(): return
        r = self._call(self.api.logout, self.username)
        if r and r.get("ok"):
            _ok(r.get("message", "Logged out"))
            self.username = None
            self.pin      = None
        elif r:
            _err(r.get("error", "Logout failed"))

    def cmd_passwd(self, args):
        if self._need_login(): return
        if len(args) >= 2:
            old, new = args[0], args[1]
        else:
            old = getpass.getpass(f"  Current password: ")
            new = getpass.getpass(f"  New password: ")
        r = self._call(self.api.change_password, self.username, old, new)
        if r and r.get("ok"):
            _ok(r.get("message", "Password changed"))
        elif r:
            _err(r.get("error", "Password change failed"))

    def cmd_whoami(self, args):
        if self._need_login(): return
        r = self._call(self.api.me, self.username)
        if r and r.get("ok"):
            admin_tag = f"  {yellow(bold('[ADMIN]'))}" if r.get("is_admin") else ""
            _info(f"User: {cyan(bold(r['username']))}{admin_tag}")
            _info(f"PIN : {bold(r.get('pin','?'))}")
        elif r:
            _err(r.get("error","Failed"))

    def cmd_chat(self, message: str):
        if self._need_login(): return
        print(f"\n  {magenta(bold('flask'))} {dim('thinking...')}", end="\r", flush=True)
        r = self._call(self.api.chat, self.username, message, self.model)
        # clear "thinking" line
        print(" " * (_tw() - 1), end="\r")
        if r:
            self._handle_chat_response(r)

    def cmd_model(self, args):
        if not args:
            _info(f"Active model: {bold(self.model)}")
            return
        self.model = args[0]
        _ok(f"Model set to {bold(self.model)}")

    def cmd_models(self, args):
        r = self._call(self.api.models)
        if r and r.get("ok"):
            default = r.get("default","")
            for name in r.get("models",[]):
                tag = f"  {yellow(bold('(default)'))}" if name == default else ""
                current = f"  {green(bold('← active'))}" if name == self.model else ""
                print(f"  {green(bold(name))}{tag}{current}")
        elif r:
            _err(r.get("error","Failed"))

    def cmd_history(self, args):
        if self._need_login(): return
        r = self._call(self.api.chat_history, self.username)
        if r and r.get("ok"):
            msgs = r.get("messages",[])
            if not msgs:
                _info("No chat history yet.")
            else:
                _print_history(msgs)
                _info(f"{len(msgs)} messages total")
        elif r:
            _err(r.get("error","Failed"))

    def cmd_load(self, args):
        if self._need_login(): return
        if not args:
            _err("Usage: load <pin>"); return
        r = self._call(self.api.chat_load, self.username, args[0])
        if r and r.get("ok"):
            _ok(r.get("message","Loaded"))
            if r.get("messages"):
                _print_history(r["messages"])
        elif r:
            _err(r.get("error","Load failed"))

    def cmd_clear(self, args):
        if self._need_login(): return
        if not _confirm("Clear all chat history?"): return
        r = self._call(self.api.chat_clear, self.username)
        if r and r.get("ok"):
            _ok(r.get("message","Cleared"))
        elif r:
            _err(r.get("error","Clear failed"))

    def cmd_export(self, args):
        if self._need_login(): return
        r = self._call(self.api.chat_export, self.username)
        if r and r.get("ok"):
            _ok(f"{r.get('message','Exported')}  →  {bold(r.get('filename',''))}")
        elif r:
            _err(r.get("error","Export failed"))

    def cmd_learn(self, args):
        if self._need_login(): return
        if not args:
            _err("Usage: learn <sentence>"); return
        sentence = " ".join(args)
        r = self._call(self.api.learn, self.username, sentence)
        if r and r.get("ok"):
            _ok("Noted.")
        elif r:
            _err(r.get("error","Failed"))

    def cmd_reset_knowledge(self, args):
        if not _confirm("Wipe and reseed the knowledge base?"): return
        r = self._call(self.api.reset_knowledge)
        if r and r.get("ok"):
            _ok(r.get("message","Done"))
        elif r:
            _err(r.get("error","Failed"))

    def cmd_files(self, args):
        r = self._call(self.api.files)
        if r and r.get("ok"):
            files = r.get("files",[])
            if not files:
                _info("No files available.")
            else:
                for f in files:
                    print(f"  {cyan(bold(f['name']))}  {dim(f.get('path',''))}")
        elif r:
            _err(r.get("error","Failed"))

    def cmd_read(self, args):
        if self._need_login(): return
        if not args:
            _err("Usage: read <filename>"); return
        r = self._call(self.api.read_file, self.username, args[0])
        if r and r.get("ok"):
            content = r.get("content","")
            print(f"\n{cyan('─'*60)}")
            print(content)
            print(f"{cyan('─'*60)}\n")
        elif r:
            _err(r.get("error","Failed"))

    def cmd_readpath(self, args):
        if self._need_login(): return
        if not args:
            _err("Usage: readpath <filepath>"); return
        r = self._call(self.api.read_path, self.username, args[0])
        if r and r.get("ok"):
            content = r.get("content","")
            print(f"\n{cyan('─'*60)}")
            print(content)
            print(f"{cyan('─'*60)}\n")
        elif r:
            _err(r.get("error","Failed"))

    def cmd_write(self, args):
        if self._need_login(): return
        if not args:
            _err("Usage: write <filename> [content]"); return
        filename = args[0]
        if len(args) > 1:
            content = " ".join(args[1:])
        else:
            content = _multiline_input(f"Enter content for {bold(filename)} (blank line to finish):")
        if not content.strip():
            _warn("No content — nothing written."); return
        r = self._call(self.api.write_file, self.username, filename, content)
        if r and r.get("ok"):
            _ok(r.get("message","Written"))
        elif r:
            _err(r.get("error","Write failed"))

    def cmd_save_block(self, args):
        lang     = input(f"  {dim('Language (e.g. python, js):')} ").strip() or "txt"
        filename = input(f"  {dim('Filename:')} ").strip()
        if not filename:
            _warn("No filename — cancelled."); return
        code = _multiline_input("Paste code (blank line to finish):")
        if not code.strip():
            _warn("No code — cancelled."); return
        r = self._call(self.api.save_block, lang, code, filename)
        if r and r.get("ok"):
            _ok(f"Saved: {bold(r.get('filename', filename))}")
        elif r:
            _err(r.get("error","Save failed"))

    def cmd_clear_outputs(self, args):
        if not _confirm("Wipe server outputs/ folder?"): return
        r = self._call(self.api.clear_outputs)
        if r and r.get("ok"):
            _ok(r.get("message","Done"))
        elif r:
            _err(r.get("error","Failed"))

    def cmd_remember(self, args):
        if self._need_login(): return
        if not args:
            _err("Usage: remember <text>"); return
        text = " ".join(args)
        r = self._call(self.api.remember, self.username, text)
        if r and r.get("ok"):
            _ok(r.get("message","Saved"))
        elif r:
            _err(r.get("error","Failed"))

    def cmd_notes(self, args):
        if self._need_login(): return
        r = self._call(self.api.notes, self.username)
        if r and r.get("ok"):
            notes = r.get("notes",[])
            if not notes:
                _info("No saved notes.")
            else:
                for i, n in enumerate(notes):
                    print(f"  {dim(str(i)+'.')} {n}")
        elif r:
            _err(r.get("error","Failed"))

    def cmd_forget(self, args):
        if self._need_login(): return
        if not args:
            _err("Usage: forget <index>"); return
        try:
            idx = int(args[0])
        except ValueError:
            _err("Index must be a number"); return
        r = self._call(self.api.forget, self.username, idx)
        if r and r.get("ok"):
            _ok(r.get("message","Forgotten"))
        elif r:
            _err(r.get("error","Failed"))

    def cmd_forget_all(self, args):
        if self._need_login(): return
        if not _confirm("Delete ALL your saved notes?"): return
        r = self._call(self.api.forget_all, self.username)
        if r and r.get("ok"):
            _ok(r.get("message","Done"))
        elif r:
            _err(r.get("error","Failed"))

    def cmd_apikey_slot(self, args):
        if self._need_login(): return
        if not args:
            _err("Usage: apikey-slot <1|2|3>"); return
        r = self._call(self.api.apikey_slot, self.username, args[0])
        if r and r.get("ok"):
            _ok(r.get("message","Done"))
        elif r:
            _err(r.get("error","Failed"))

    def cmd_apikey_groq(self, args):
        if self._need_login(): return
        key = args[0] if args else getpass.getpass("  Groq API key: ")
        r = self._call(self.api.apikey_groq, self.username, key)
        if r and r.get("ok"):
            _ok(r.get("message","Saved"))
        elif r:
            _err(r.get("error","Failed"))

    def cmd_apikey_openrouter(self, args):
        if self._need_login(): return
        key = args[0] if args else getpass.getpass("  OpenRouter API key: ")
        r = self._call(self.api.apikey_openrouter, self.username, key)
        if r and r.get("ok"):
            _ok(r.get("message","Saved"))
        elif r:
            _err(r.get("error","Failed"))

    def cmd_ping(self, args):
        if self._need_login(): return
        r = self._call(self.api.ping, self.username, self.model)
        if r:
            symbol = green(bold("✓")) if r.get("ok") else red(bold("✗"))
            print(f"  {symbol} {r.get('provider','')}  {r.get('message','')}")

    def cmd_health(self, args):
        r = self._call(self.api.health)
        if r and r.get("ok"):
            k = r.get("knowledge",{})
            print(f"  {green(bold('status'))}   {r.get('status','?')}")
            print(f"  {dim('words')}     {k.get('words','?')}")
            print(f"  {dim('bigrams')}   {k.get('bigrams','?')}")
            print(f"  {dim('trigrams')}  {k.get('trigrams','?')}")
            print(f"  {dim('debug')}     {r.get('debug_mode','?')}")
        elif r:
            _err(r.get("error","Failed"))

    def cmd_stats(self, args):
        if self._need_login(): return
        r = self._call(self.api.stats, self.username, self.model)
        if r and r.get("ok"):
            print(f"  {dim('model')}      {bold(r.get('model','?'))}")
            print(f"  {dim('provider')}   {r.get('provider','?')}")
            print(f"  {dim('has key')}    {green('yes') if r.get('has_api_key') else red('no')}")
            print(f"  {dim('words')}      {r.get('words','?')}")
        elif r:
            _err(r.get("error","Failed"))

    def cmd_clock(self, args):
        if self._need_login(): return
        r = self._call(self.api.clock, self.username, self.model)
        if r and r.get("ok"):
            print(f"  {cyan(bold(r.get('system_time','?')))}")
            if r.get("answer"):
                _print_answer(r["answer"])
        elif r:
            _err(r.get("error","Failed"))

    def cmd_debug(self, args):
        if args and args[0].lower() == "on":
            r = self._call(self.api.debug_on)
            self._debug_local = True
        elif args and args[0].lower() == "off":
            r = self._call(self.api.debug_off)
            self._debug_local = False
        else:
            # toggle local debug display
            self._debug_local = not self._debug_local
            r = (self._call(self.api.debug_on) if self._debug_local
                 else self._call(self.api.debug_off))
        if r and r.get("ok"):
            state = green(bold("ON")) if self._debug_local else yellow(bold("OFF"))
            _ok(f"Debug mode {state}")

    # ── dispatch ──────────────────────────────────────────────────────────

    def dispatch(self, raw: str) -> bool:
        """Process one REPL line. Returns False to exit."""
        line = raw.strip()
        if not line:
            return True

        parts  = line.split()
        cmd    = parts[0].lower()
        args   = parts[1:]
        rest   = " ".join(args)

        if cmd in ("exit", "quit"):
            if self.username:
                self.cmd_logout([])
            print(f"\n{cyan(bold('Bye!'))} See you next session.\n")
            return False

        elif cmd == "help":
            print(HELP_TEXT)

        elif cmd == "register":
            self.cmd_register(args)

        elif cmd == "login":
            if parts[1:2] == ["pin"] or (len(parts) == 2 and len(parts[1]) == 6):
                # allow "login-pin <pin>" as alias "login pin <pin>"
                self.cmd_login_pin(args[1:] or args)
            else:
                self.cmd_login(args)

        elif cmd == "login-pin":
            self.cmd_login_pin(args)

        elif cmd == "logout":
            self.cmd_logout(args)

        elif cmd == "passwd":
            self.cmd_passwd(args)

        elif cmd == "whoami":
            self.cmd_whoami(args)

        elif cmd == "model":
            self.cmd_model(args)

        elif cmd == "models":
            self.cmd_models(args)

        elif cmd == "history":
            self.cmd_history(args)

        elif cmd == "load":
            self.cmd_load(args)

        elif cmd == "clear" and not args:
            self.cmd_clear(args)

        elif cmd == "export":
            self.cmd_export(args)

        elif cmd == "learn":
            self.cmd_learn(args)

        elif cmd == "reset-knowledge":
            self.cmd_reset_knowledge(args)

        elif cmd == "files":
            self.cmd_files(args)

        elif cmd == "read":
            self.cmd_read(args)

        elif cmd == "readpath":
            self.cmd_readpath(args)

        elif cmd == "write":
            self.cmd_write(args)

        elif cmd == "save-block":
            self.cmd_save_block(args)

        elif cmd == "clear-outputs":
            self.cmd_clear_outputs(args)

        elif cmd == "remember":
            self.cmd_remember(args)

        elif cmd == "notes":
            self.cmd_notes(args)

        elif cmd == "forget":
            if args and args[0].lower() == "all":
                self.cmd_forget_all([])
            else:
                self.cmd_forget(args)

        elif cmd == "forget-all":
            self.cmd_forget_all(args)

        elif cmd == "apikey-slot":
            self.cmd_apikey_slot(args)

        elif cmd == "apikey-groq":
            self.cmd_apikey_groq(args)

        elif cmd == "apikey-openrouter":
            self.cmd_apikey_openrouter(args)

        elif cmd == "ping":
            self.cmd_ping(args)

        elif cmd == "health":
            self.cmd_health(args)

        elif cmd == "stats":
            self.cmd_stats(args)

        elif cmd == "clock":
            self.cmd_clock(args)

        elif cmd == "debug":
            self.cmd_debug(args)

        else:
            # anything not a command → send as chat message
            if self._need_login():
                _info(f"Unknown command: {bold(cmd)}  (type {green('help')})")
            else:
                self.cmd_chat(line)

        return True


# ── entry point ──────────────────────────────────────────────────────────────

def _parse_host(spec: str) -> tuple[str, int]:
    """Parse HOST@PORT → ('host', port)."""
    if "@" not in spec:
        print(red(bold(f"Error: expected HOST@PORT, got: {spec}")))
        sys.exit(1)
    host_part, _, port_part = spec.partition("@")
    host = host_part.strip()
    try:
        port = int(port_part.strip())
    except ValueError:
        print(red(bold(f"Error: invalid port: {port_part!r}")))
        sys.exit(1)
    return host, port


def main():
    parser = argparse.ArgumentParser(
        prog="flaskcc",
        description="FlaskCode Client — connect to a FlaskCode-Server",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=textwrap.dedent("""\
        Examples:
          python flaskcc.py 192.168.1.5@5000
          python flaskcc.py localhost@5000 --pass mySecret
          python flaskcc.py myserver.local@8080 --pass abc123 --user alice
        """),
    )
    parser.add_argument("host",
                        metavar="HOST@PORT",
                        help="Server address in HOST@PORT format")
    parser.add_argument("--pass", "-p",
                        dest="password",
                        default="",
                        metavar="PASSWORD",
                        help="Server connection password (from server_config)")
    parser.add_argument("--user", "-u",
                        dest="username",
                        default="",
                        metavar="USERNAME",
                        help="Auto-login with this username (will prompt for password)")
    parser.add_argument("--no-encrypt",
                        action="store_true",
                        help="Send password in plain text (don't hash)")
    args = parser.parse_args()

    host, port = _parse_host(args.host)
    base_url = f"http://{host}:{port}"

    # ── probe server ──────────────────────────────────────────────────────
    print(f"\n{dim('Connecting to')} {cyan(bold(base_url))} {dim('...')}")
    api = FlaskCodeClient(base_url, token="")

    try:
        health = api.get("/health")
        if not health.get("ok"):
            print(red(bold(f"Server error: {health.get('error','?')}")))
            sys.exit(1)
    except APIError as e:
        print(red(bold(f"Cannot reach server: {e}")))
        sys.exit(1)

    # ── derive auth token ─────────────────────────────────────────────────
    raw_password = args.password
    if raw_password:
        if args.no_encrypt:
            token = raw_password
        else:
            method = health.get("encryption_method", "SHA256")
            encrypt = health.get("encrypt", True)
            if isinstance(encrypt, str):
                encrypt = encrypt.lower() not in ("false", "0", "no")
            token = _derive_token(raw_password, method, encrypt)
        api.token = token
        # verify the token works (ping /health again with it)
        try:
            check = api.get("/health")
            if not check.get("ok"):
                print(red(bold(f"Auth failed: {check.get('error','Bad password')}")))
                sys.exit(1)
        except APIError as e:
            print(red(bold(f"Auth error: {e}")))
            sys.exit(1)
        _ok(f"Authenticated to {cyan(bold(base_url))}")
    else:
        _ok(f"Connected to {cyan(bold(base_url))} {dim('(no password)')}")

    # ── start session ─────────────────────────────────────────────────────
    print(BANNER)
    session = Session(api)

    # Auto-login if --user was passed
    if args.username:
        pw = getpass.getpass(f"  Password for {bold(args.username)}: ")
        session.cmd_login([args.username, pw])

    # ── REPL ──────────────────────────────────────────────────────────────
    prompt_base = cyan(bold("flask›"))
    while True:
        try:
            user_label = f"{magenta(bold(session.username))}@" if session.username else ""
            model_label = dim(f"[{session.model}]")
            raw = input(f"\n{user_label}{prompt_base} {model_label} ")
        except (KeyboardInterrupt, EOFError):
            print()
            if session.username:
                session.cmd_logout([])
            print(f"{cyan(bold('Bye!'))} See you next session.\n")
            break

        if not session.dispatch(raw):
            break


if __name__ == "__main__":
    main()

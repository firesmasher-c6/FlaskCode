"""
FlaskCode-Server  (Linux only, terminal/CLI — no GUI)
=====================================================
Exposes every FlaskCode feature as a Flask REST API.
A future client app connects to this server over HTTP.

Endpoints
---------
POST /auth/register          {username, password}
POST /auth/login             {username, password}
POST /auth/logout            {username}   — saves chat, returns ok
POST /auth/change-password   {username, current_password, new_password}

GET  /me                     ?username=<u>   — whoami + pin
GET  /stats                  ?username=<u>&model=<m>

POST /chat                   {username, message, model?}  — main chat
POST /chat/load              {username, pin}
POST /chat/clear             {username}
POST /chat/export            {username}
GET  /chat/history           ?username=<u>

POST /learn                  {username, sentence}
POST /reset-knowledge        {}

GET  /files                  ?username=<u>
POST /files/read             {username, filename}
POST /files/read-path        {username, filepath}
POST /files/write            {username, filename, content}
POST /files/clear-outputs    {}

POST /apikey/set-slot        {username, slot}   (1/2/3 — Gemini)
POST /apikey/set-groq        {username, key}
POST /apikey/set-openrouter  {username, key}

POST /ping                   {username, model?}

POST /debug/on               {}   (server-side toggle)
POST /debug/off              {}

GET  /health                 — liveness check
"""

import os
import sys
import re
import time
import random
import threading
from functools import wraps

from flask import Flask, request, jsonify
import server_config as _server_config

from engine import KnowledgeEngine
import gemini_client
import groq_client
import openrouter_client
import apikey_settings
import auth
import chat_history
import saved_info
from file_handler import (
    list_available_files, process_file_for_ai, write_file,
    clear_outputs, read_filepath_for_ai,
)
from code_extractor import (
    classify_blocks, strip_action_directives, save_code_block, resolve_extension,
)
from chat_loader import load_chat_history, save_chat_history, format_history_for_ai
import shell_actions

# ── constants ──────────────────────────────────────────────────────────────

ADMIN_USERNAME = "admin"
MIN_LEARN_WORDS = 4
MIN_THINK_TIME = 0.5
MAX_ACTION_ROUNDS = 3
WARN_30S = 30
WARN_2MIN = 120
TIMEOUT_20MIN = 1200

MODELS = {
    "3.5-flash":      ("gemini", "3.5-flash"),
    "3.1-flash":      ("gemini", "3-flash"),
    "3.1-flash-lite": ("gemini", "3.1-flash-lite"),
    "gpt-oss-20b":    ("openrouter", "openai/gpt-oss-20b:free"),
    "llama-3.3-70b":  ("groq", "llama-3.3-70b-versatile"),
}
DEFAULT_MODEL = "3.1-flash-lite"

CLIENTS = {
    "gemini": gemini_client,
    "groq": groq_client,
    "openrouter": openrouter_client,
}

# ── server state ───────────────────────────────────────────────────────────

app = Flask(__name__)
engine = KnowledgeEngine()
debug_mode = False          # toggled by /debug/on and /debug/off

# ── server config (password + encryption) ─────────────────────────────────
_SERVER_DIR   = os.path.dirname(os.path.abspath(__file__))
_CONF         = _server_config.load(_SERVER_DIR)
_REQUIRE_AUTH = _CONF["password"] not in ("", "000000")

@app.before_request
def _check_server_password():
    """Validate X-FlaskCode-Token header if a password is configured."""
    if request.path in ("/health",):
        return None
    if not _REQUIRE_AUTH:
        return None
    token = request.headers.get("X-FlaskCode-Token", "")
    if not _server_config.verify_token(token, _CONF):
        return jsonify(ok=False, error="Unauthorized: bad server password"), 401
    return None

# ── helpers ────────────────────────────────────────────────────────────────

def _provider_for(model_name: str) -> str:
    return MODELS.get(model_name, MODELS[DEFAULT_MODEL])[0]

def _model_id_for(model_name: str) -> str:
    return MODELS.get(model_name, MODELS[DEFAULT_MODEL])[1]

def _client_for(model_name: str):
    return CLIENTS[_provider_for(model_name)]

def _with_saved_info(context: dict, username: str) -> dict:
    if username:
        context["username"] = username
        context["is_admin"] = username.lower() == ADMIN_USERNAME
        notes = saved_info.format_for_ai(username)
        if notes:
            context["saved_info"] = notes
    return context

def _format_debug_line(debug_info) -> str:
    if not debug_info:
        return "[debug] no API key used — local engine answered"
    attempts = debug_info.get("attempts") or []
    used_label = debug_info.get("used_label")
    used_masked = debug_info.get("used_key_masked")
    if used_label:
        line = f"[debug] responded via {used_label} ({used_masked})"
        if len(attempts) > 1:
            failed = ", ".join(attempts[:-1])
            line += f" -- retried after {failed} failed"
        return line
    tried = ", ".join(attempts) if attempts else "(none)"
    return f"[debug] all apikeys failed -- tried: {tried}"

def _format_directive_debug(rounds) -> str:
    entries = []
    multi = len(rounds) > 1
    for round_num, blocks in rounds:
        for b in blocks:
            directive = b.get("directive")
            if not directive:
                continue
            prefix = f"round {round_num} -- " if multi else ""
            entries.append(f"  {prefix}{directive}")
    if not entries:
        return "[debug] no hidden directives in this response"
    return "[debug] hidden directive(s):\n" + "\n".join(entries)

def _save_write_blocks(write_blocks):
    saved = []
    for b in write_blocks:
        success, msg = save_code_block(b["language"], b["code"], b["filename"])
        if success:
            saved.append(b["filename"])
    return saved

def _think(user_input: str, context: dict, model: str = DEFAULT_MODEL):
    """
    Call the AI (or fall back to local engine). Returns (answer, err, debug_info).
    Runs synchronously inside a thread with a timeout guard.
    """
    result = {"answer": None, "err": None, "debug_info": None, "timed_out": False}
    client = _client_for(model)
    model_id = _model_id_for(model)
    username = context.get("username")

    def worker():
        answer = None
        if client.has_api_key(username):
            answer, err, debug_info = client.ask(user_input, context, model=model_id)
            result["err"] = err
            result["debug_info"] = debug_info
        if answer is None:
            answer = engine.generate(seed=context.get("seed"))
        result["answer"] = answer

    t = threading.Thread(target=worker, daemon=True)
    t.start()
    t.join(timeout=TIMEOUT_20MIN)
    if t.is_alive():
        result["timed_out"] = True
        result["err"] = "cancelled: exceeded 20-minute timeout"

    return result["answer"], result["err"], result["debug_info"]

def _run_ai_action_loop(user_input: str, context: dict, model: str):
    """
    Same logic as the original client — but instead of interactively asking
    the user on the console, we return the pending action to the caller so
    the HTTP client can confirm it and POST back.  For now: auto-confirm
    run/read actions (the operator controls what connects to this server).
    Returns (answer, err, debug_info, write_blocks, plain_blocks, action_log, rounds).
    """
    action_log = []
    rounds = []
    current_message = user_input
    working_context = dict(context)
    answer, err, debug_info = None, None, None

    for round_num in range(MAX_ACTION_ROUNDS):
        answer, err, debug_info = _think(current_message, working_context, model=model)
        if not answer:
            break

        blocks = classify_blocks(answer)
        rounds.append((round_num + 1, blocks))
        actionable = [b for b in blocks if b["kind"] in ("run", "read")]
        if not actionable:
            break

        if round_num == MAX_ACTION_ROUNDS - 1:
            action_log.append(
                f"stopped after {MAX_ACTION_ROUNDS} action round(s) — "
                "Flask asked for more, so its last request was left unrun"
            )
            break

        tool_results = []
        for b in actionable:
            if b["kind"] == "run":
                ok, output = shell_actions.run_command(
                    b["command"], cwd=b.get("cwd"), executor=b.get("executor")
                )
                mark = "✓" if ok else "✗"
                action_log.append(f"{mark} ran: {b['command']}")
                action_log.append(f"    {output}")
                tool_results.append(f'Output of `{b["command"]}`:\n{output}')
            else:  # read
                path = b.get("path") or "(no path given)"
                ok, content = shell_actions.read_arbitrary_file(b.get("path"))
                mark = "✓" if ok else "✗"
                action_log.append(f"{mark} read: {path}")
                if ok:
                    action_log.append(f"    {content[:200]}...")
                    tool_results.append(f"Contents of {path}:\n{content}")
                else:
                    tool_results.append(f"Could not read {path}: {content}")

        working_context = dict(context)
        working_context["tool_results"] = tool_results
        current_message = (
            "Here are the results of the action(s) you requested. Use them to give your "
            "real answer now -- don't request the same action again unless it's genuinely necessary."
        )

    final_blocks = rounds[-1][1] if rounds else []
    write_blocks = [b for b in final_blocks if b["kind"] == "write"]
    plain_blocks = [b for b in final_blocks if b["kind"] == "plain"]

    return answer, err, debug_info, write_blocks, plain_blocks, action_log, rounds

def _require_fields(*fields):
    """Decorator that checks JSON body contains required fields."""
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            data = request.get_json(silent=True) or {}
            missing = [f for f in fields if not data.get(f)]
            if missing:
                return jsonify(ok=False, error=f"Missing required field(s): {', '.join(missing)}"), 400
            return fn(*args, **kwargs)
        return wrapper
    return decorator

# ── auth endpoints ─────────────────────────────────────────────────────────

@app.route("/auth/register", methods=["POST"])
@_require_fields("username", "password")
def route_register():
    data = request.get_json()
    success, msg = auth.register(data["username"], data["password"])
    if success:
        pin = chat_history.get_user_pin(data["username"])
        return jsonify(ok=True, message=msg, pin=pin)
    return jsonify(ok=False, error=msg), 400


@app.route("/auth/login", methods=["POST"])
@_require_fields("username", "password")
def route_login():
    data = request.get_json()
    username = data["username"]
    success, msg = auth.login(username, data["password"])
    if not success:
        return jsonify(ok=False, error=msg), 401
    pin = chat_history.get_user_pin(username)
    messages = load_chat_history(username)
    return jsonify(ok=True, message=msg, pin=pin, history_count=len(messages))


@app.route("/auth/logout", methods=["POST"])
@_require_fields("username")
def route_logout():
    data = request.get_json()
    username = data["username"]
    messages = load_chat_history(username)
    if messages:
        ok, save_msg, _ = chat_history.save_chat(username, messages)
        return jsonify(ok=True, message=f"Logged out. {save_msg}")
    return jsonify(ok=True, message="Logged out.")


@app.route("/auth/change-password", methods=["POST"])
@_require_fields("username", "current_password", "new_password")
def route_change_password():
    data = request.get_json()
    success, msg = auth.change_password(
        data["username"], data["current_password"], data["new_password"]
    )
    if success:
        return jsonify(ok=True, message=msg)
    return jsonify(ok=False, error=msg), 400


@app.route("/auth/login-pin", methods=["POST"])
@_require_fields("pin")
def route_login_pin():
    data = request.get_json()
    username = chat_history.find_user_by_pin(data["pin"])
    if not username:
        return jsonify(ok=False, error="No account matches that PIN"), 401
    pin = chat_history.get_user_pin(username)
    messages = load_chat_history(username)
    return jsonify(ok=True, username=username, pin=pin, history_count=len(messages))

# ── me / stats ─────────────────────────────────────────────────────────────

@app.route("/me", methods=["GET"])
def route_me():
    username = request.args.get("username", "").strip()
    if not username:
        return jsonify(ok=False, error="username param required"), 400
    pin = chat_history.get_user_pin(username)
    is_admin = username.lower() == ADMIN_USERNAME
    return jsonify(ok=True, username=username, pin=pin, is_admin=is_admin)


@app.route("/stats", methods=["GET"])
def route_stats():
    username = request.args.get("username", "").strip()
    model = request.args.get("model", DEFAULT_MODEL)
    words, bigrams, trigrams = engine.stats()
    provider = _provider_for(model)
    client = _client_for(model)
    has_key = client.has_api_key(username) if username else False
    return jsonify(
        ok=True,
        words=words,
        bigrams=bigrams,
        trigrams=trigrams,
        model=model,
        provider=provider,
        has_api_key=has_key,
    )

# ── chat ───────────────────────────────────────────────────────────────────

@app.route("/chat", methods=["POST"])
@_require_fields("username", "message")
def route_chat():
    data = request.get_json()
    username = data["username"]
    user_input = data["message"].strip()
    model = data.get("model", DEFAULT_MODEL)

    if not user_input:
        return jsonify(ok=False, error="message is empty"), 400

    context = engine.context_for(user_input)
    context = _with_saved_info(context, username)

    # Include chat history in context
    messages = load_chat_history(username)
    history = format_history_for_ai(messages)
    if history:
        context["chat_history"] = history

    if len(user_input.split()) >= MIN_LEARN_WORDS:
        engine.learn(user_input)

    # Track user message
    messages.append({
        "role": "user",
        "text": user_input,
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
    })

    answer, err, debug_info, write_blocks, plain_blocks, action_log, rounds = \
        _run_ai_action_loop(user_input, context, model)

    response_payload = {
        "ok": True,
        "answer": None,
        "error": err,
        "action_log": action_log,
        "saved_files": [],
        "plain_blocks": [],
        "debug": None,
    }

    if answer:
        # Track AI message
        messages.append({
            "role": "flask",
            "text": answer,
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        })

        clean_answer = strip_action_directives(answer)
        response_payload["answer"] = clean_answer

        saved = _save_write_blocks(write_blocks)
        response_payload["saved_files"] = saved

        # Return plain blocks so client can ask user whether to save
        response_payload["plain_blocks"] = [
            {"language": b["language"], "code": b["code"]} for b in plain_blocks
        ]

        if debug_mode:
            response_payload["debug"] = {
                "api_key_info": _format_debug_line(debug_info),
                "directives": _format_directive_debug(rounds),
            }

        # Auto-save chat
        chat_history.save_chat(username, messages)
        save_chat_history(username, messages)

    elif err:
        response_payload["ok"] = False

    return jsonify(response_payload)


@app.route("/chat/history", methods=["GET"])
def route_chat_history():
    username = request.args.get("username", "").strip()
    if not username:
        return jsonify(ok=False, error="username param required"), 400
    messages = load_chat_history(username)
    return jsonify(ok=True, messages=messages, count=len(messages))


@app.route("/chat/load", methods=["POST"])
@_require_fields("username", "pin")
def route_chat_load():
    data = request.get_json()
    success, messages, msg = chat_history.load_chat(data["username"], data["pin"])
    if success and messages:
        return jsonify(ok=True, message=msg, messages=messages, count=len(messages))
    return jsonify(ok=False, error=msg), 404


@app.route("/chat/clear", methods=["POST"])
@_require_fields("username")
def route_chat_clear():
    data = request.get_json()
    username = data["username"]
    ok, save_msg, _ = chat_history.save_chat(username, [])
    save_chat_history(username, [])
    if ok:
        return jsonify(ok=True, message="Chat history cleared")
    return jsonify(ok=False, error=save_msg), 500


@app.route("/chat/export", methods=["POST"])
@_require_fields("username")
def route_chat_export():
    data = request.get_json()
    username = data["username"]
    messages = load_chat_history(username)
    if not messages:
        return jsonify(ok=False, error="Nothing to export — chat is empty"), 400

    lines = [
        "FlaskCode Chat Export",
        f"User: {username}",
        f"Exported: {time.strftime('%Y-%m-%d %H:%M:%S')}",
        "=" * 60,
        "",
    ]
    for msg in messages:
        role = msg.get("role", "unknown")
        text = msg.get("text", "")
        timestamp = msg.get("timestamp", "")
        speaker = "you" if role == "user" else "flask"
        lines.append(f"{speaker}> {text} [{timestamp}]")

    export_filename = f"chat_export_{username}_{time.strftime('%Y%m%d_%H%M%S')}.txt"
    success, file_msg = write_file(export_filename, "\n".join(lines))
    if success:
        return jsonify(ok=True, message=file_msg, filename=export_filename)
    return jsonify(ok=False, error=file_msg), 500

# ── knowledge ──────────────────────────────────────────────────────────────

@app.route("/learn", methods=["POST"])
@_require_fields("username", "sentence")
def route_learn():
    data = request.get_json()
    sentence = data["sentence"].strip()
    if not sentence:
        return jsonify(ok=False, error="sentence is empty"), 400
    engine.learn(sentence)
    return jsonify(ok=True, message="Noted.")


@app.route("/reset-knowledge", methods=["POST"])
def route_reset_knowledge():
    engine.reset()
    return jsonify(ok=True, message="Knowledge base wiped and reseeded.")

# ── file endpoints ─────────────────────────────────────────────────────────

@app.route("/files", methods=["GET"])
def route_list_files():
    files = list_available_files()
    return jsonify(ok=True, files=[
        {"name": f["name"], "path": f["path"], "ext": f["ext"]}
        for f in files
    ])


@app.route("/files/read", methods=["POST"])
@_require_fields("username", "filename")
def route_read_file():
    data = request.get_json()
    content, err = process_file_for_ai(data["filename"])
    if err:
        return jsonify(ok=False, error=err), 404
    return jsonify(ok=True, content=content)


@app.route("/files/read-path", methods=["POST"])
@_require_fields("username", "filepath")
def route_read_filepath():
    data = request.get_json()
    content, err = read_filepath_for_ai(data["filepath"])
    if err:
        return jsonify(ok=False, error=err), 400
    return jsonify(ok=True, content=content)


@app.route("/files/write", methods=["POST"])
@_require_fields("username", "filename", "content")
def route_write_file():
    data = request.get_json()
    success, msg = write_file(data["filename"], data["content"])
    if success:
        return jsonify(ok=True, message=msg)
    return jsonify(ok=False, error=msg), 500


@app.route("/files/clear-outputs", methods=["POST"])
def route_clear_outputs():
    success, msg = clear_outputs()
    if success:
        return jsonify(ok=True, message=msg)
    return jsonify(ok=False, error=msg), 500

# ── saved info (remember/forget) ───────────────────────────────────────────

@app.route("/remember", methods=["POST"])
@_require_fields("username", "text")
def route_remember():
    data = request.get_json()
    success, msg = saved_info.remember(data["username"], data["text"])
    if success:
        return jsonify(ok=True, message=msg)
    return jsonify(ok=False, error=msg), 400


@app.route("/remember", methods=["GET"])
def route_list_remember():
    username = request.args.get("username", "").strip()
    if not username:
        return jsonify(ok=False, error="username param required"), 400
    notes = saved_info.list_notes(username)
    return jsonify(ok=True, notes=notes)


@app.route("/remember/forget", methods=["POST"])
@_require_fields("username", "index")
def route_forget():
    data = request.get_json()
    try:
        idx = int(data["index"])
    except (ValueError, TypeError):
        return jsonify(ok=False, error="index must be an integer"), 400
    success, msg = saved_info.forget(data["username"], idx)
    if success:
        return jsonify(ok=True, message=msg)
    return jsonify(ok=False, error=msg), 400


@app.route("/remember/forget-all", methods=["POST"])
@_require_fields("username")
def route_forget_all():
    data = request.get_json()
    success, msg = saved_info.forget_all(data["username"])
    if success:
        return jsonify(ok=True, message=msg)
    return jsonify(ok=False, error=msg), 500

# ── apikey management ──────────────────────────────────────────────────────

@app.route("/apikey/set-slot", methods=["POST"])
@_require_fields("username", "slot")
def route_apikey_set_slot():
    data = request.get_json()
    try:
        slot = int(data["slot"])
    except (ValueError, TypeError):
        return jsonify(ok=False, error="slot must be 1, 2, or 3"), 400
    success, msg = apikey_settings.set_selected_key(data["username"], slot)
    if success:
        return jsonify(ok=True, message=msg)
    return jsonify(ok=False, error=msg), 400


@app.route("/apikey/set-groq", methods=["POST"])
@_require_fields("username", "key")
def route_apikey_set_groq():
    data = request.get_json()
    success, msg = apikey_settings.set_groq_key(data["username"], data["key"])
    if success:
        return jsonify(ok=True, message=msg)
    return jsonify(ok=False, error=msg), 400


@app.route("/apikey/set-openrouter", methods=["POST"])
@_require_fields("username", "key")
def route_apikey_set_openrouter():
    data = request.get_json()
    success, msg = apikey_settings.set_openrouter_key(data["username"], data["key"])
    if success:
        return jsonify(ok=True, message=msg)
    return jsonify(ok=False, error=msg), 400

# ── ping / debug ───────────────────────────────────────────────────────────

@app.route("/ping", methods=["POST"])
def route_ping():
    data = request.get_json(silent=True) or {}
    username = data.get("username", "")
    model = data.get("model", DEFAULT_MODEL)
    client = _client_for(model)
    provider = _provider_for(model).capitalize()
    ok, msg = client.ping(username=username)
    return jsonify(ok=ok, provider=provider, message=msg)


@app.route("/debug/on", methods=["POST"])
def route_debug_on():
    global debug_mode  # noqa: PLW0603
    debug_mode = True
    return jsonify(ok=True, message="Debug mode ON")


@app.route("/debug/off", methods=["POST"])
def route_debug_off():
    global debug_mode
    debug_mode = False
    return jsonify(ok=True, message="Debug mode OFF")


@app.route("/health", methods=["GET"])
def route_health():
    words, bigrams, trigrams = engine.stats()
    return jsonify(
        ok=True,
        status="running",
        knowledge={"words": words, "bigrams": bigrams, "trigrams": trigrams},
        debug_mode=debug_mode,
        encrypt=_CONF["encrypt"],
        encryption_method=_CONF["encryption_method"],
        password_required=_REQUIRE_AUTH,
    )


@app.route("/models", methods=["GET"])
def route_models():
    return jsonify(ok=True, models=list(MODELS.keys()), default=DEFAULT_MODEL)

# ── clock (secret feature port) ────────────────────────────────────────────

@app.route("/clock", methods=["GET"])
def route_clock():
    now_str = time.strftime("%Y-%m-%d %H:%M:%S")
    username = request.args.get("username", "")
    model = request.args.get("model", DEFAULT_MODEL)
    clock_prompt = (
        f"What time is it right now? The system clock currently reads exactly: {now_str}. "
        f"State the current time clearly and naturally."
    )
    context = engine.context_for(clock_prompt)
    if username:
        context["username"] = username
    answer, err, _ = _think(clock_prompt, context, model=model)
    return jsonify(
        ok=True,
        system_time=now_str,
        answer=answer or f"It is currently {now_str}",
        error=err,
    )

# ── save a plain code block (client-side confirmation flow) ────────────────

@app.route("/files/save-block", methods=["POST"])
@_require_fields("language", "code", "filename")
def route_save_block():
    data = request.get_json()
    success, msg = save_code_block(data["language"], data["code"], data["filename"])
    if success:
        return jsonify(ok=True, message=msg, filename=data["filename"])
    return jsonify(ok=False, error=msg), 500


# ── CLI admin console (runs in the same process as the server) ─────────────

RESET    = "\033[0m"
BOLD     = "\033[1m"
DIM      = "\033[2m"
CYAN     = "\033[96m"
MAGENTA  = "\033[95m"
GREEN    = "\033[92m"
YELLOW   = "\033[93m"
RED      = "\033[91m"
GRAY     = "\033[90m"
BLUE     = "\033[94m"

BANNER = f"""{CYAN}{BOLD}
╔══════════════════════════════════════════════════════════╗
║                                                          ║
║     {MAGENTA}{BOLD}F L A S K   C O D E  — S E R V E R{CYAN}              ║
║     {BLUE}{BOLD}>> Linux CLI + Flask REST API <<{CYAN}                  ║
║                                                          ║
╚══════════════════════════════════════════════════════════╝{RESET}
{YELLOW}{BOLD}ADMIN COMMANDS:{RESET}
  {GREEN}{BOLD}status{RESET}              server health + knowledge stats
  {GREEN}{BOLD}debug on/off{RESET}        toggle debug output in API responses
  {GREEN}{BOLD}learn <text>{RESET}        teach the knowledge engine something
  {GREEN}{BOLD}reset{RESET}               wipe + reseed knowledge base
  {GREEN}{BOLD}users{RESET}               list registered users
  {GREEN}{BOLD}chats{RESET}               list saved chats
  {GREEN}{BOLD}clear-outputs{RESET}       wipe the outputs/ folder
  {GREEN}{BOLD}models{RESET}              list available AI models
  {GREEN}{BOLD}help{RESET}                show this menu
  {GREEN}{BOLD}exit / quit{RESET}         stop the server
{CYAN}{BOLD}╔══════════════════════════════════════════════════════════╝{RESET}
"""

SEPARATOR = f"{CYAN}{BOLD}{'─' * 60}{RESET}"


def _admin_console(host: str, port: int):
    """Runs in a background thread — provides a local CLI while the server is up."""
    time.sleep(0.5)   # let Flask finish startup output first
    print(BANNER)
    print(f"{GREEN}{BOLD}✓{RESET} Server listening on {CYAN}http://{host}:{port}{RESET}")
    print(f"{DIM}Type {RESET}{GREEN}{BOLD}help{RESET}{DIM} for admin commands.{RESET}\n")

    while True:
        try:
            print(SEPARATOR)
            raw = input(f"{MAGENTA}{BOLD}admin›{RESET} ").strip()
        except (KeyboardInterrupt, EOFError):
            print(f"\n{YELLOW}{BOLD}⊘  Shutting down...{RESET}")
            os._exit(0)

        if not raw:
            continue

        cmd = raw.lower()

        if cmd in ("exit", "quit"):
            print(f"{YELLOW}{BOLD}⊘  Shutting down server.{RESET}")
            os._exit(0)

        elif cmd == "help":
            print(BANNER)

        elif cmd == "status":
            words, bigrams, trigrams = engine.stats()
            print(f"{GRAY}knowledge:{RESET} words={BOLD}{words}{RESET}  bigrams={BOLD}{bigrams}{RESET}  trigrams={BOLD}{trigrams}{RESET}")
            print(f"{GRAY}debug mode:{RESET} {BOLD}{debug_mode}{RESET}")

        elif cmd == "debug on":
            debug_mode = True
            print(f"{GREEN}{BOLD}✓{RESET} Debug mode ON")

        elif cmd == "debug off":
            debug_mode = False
            print(f"{YELLOW}{BOLD}↻{RESET} Debug mode OFF")

        elif cmd.startswith("learn "):
            sentence = raw[6:].strip()
            if sentence:
                engine.learn(sentence)
                print(f"{GREEN}{BOLD}→{RESET} Noted.")
            else:
                print(f"{RED}{BOLD}✗{RESET} Nothing to learn")

        elif cmd == "reset":
            engine.reset()
            print(f"{YELLOW}{BOLD}↻{RESET} Knowledge base wiped and reseeded")

        elif cmd == "users":
            import auth as _auth
            users = _auth._load_users()
            if users:
                for name in users:
                    pin = chat_history.get_user_pin(name)
                    print(f"  {CYAN}{BOLD}{name}{RESET}  pin={DIM}{pin}{RESET}")
            else:
                print(f"{DIM}No users registered yet.{RESET}")

        elif cmd == "chats":
            chats = chat_history.list_chats()
            if chats:
                for c in chats:
                    print(f"  {CYAN}{BOLD}{c['username']}{RESET}  pin={DIM}{c['pin']}{RESET}  created={DIM}{c.get('created','?')}{RESET}")
            else:
                print(f"{DIM}No chats saved yet.{RESET}")

        elif cmd == "clear-outputs":
            success, msg = clear_outputs()
            print(f"{GREEN if success else RED}{BOLD}{'✓' if success else '✗'}{RESET} {msg}")

        elif cmd == "models":
            for name, (provider, model_id) in MODELS.items():
                default_tag = f" {YELLOW}(default){RESET}" if name == DEFAULT_MODEL else ""
                print(f"  {GREEN}{BOLD}{name}{RESET}  {DIM}→ {provider}/{model_id}{RESET}{default_tag}")

        else:
            print(f"{RED}{BOLD}✗{RESET} Unknown command: {raw}  (type {GREEN}help{RESET})")


# ── entry point ────────────────────────────────────────────────────────────

def main():
    import argparse
    parser = argparse.ArgumentParser(description="FlaskCode-Server")
    parser.add_argument("--host", default="127.0.0.1", help="Bind host (default: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=5000, help="Port (default: 5000)")
    parser.add_argument("--public", action="store_true", help="Bind to 0.0.0.0 (all interfaces)")
    parser.add_argument("--no-console", action="store_true", help="Disable the admin console thread")
    args = parser.parse_args()

    host = "0.0.0.0" if args.public else args.host
    port = args.port

    if not args.no_console:
        console_thread = threading.Thread(target=_admin_console, args=(host, port), daemon=True)
        console_thread.start()

    # Suppress Flask's default reloader noise; use single-process mode
    app.run(host=host, port=port, debug=False, use_reloader=False)


if __name__ == "__main__":
    main()

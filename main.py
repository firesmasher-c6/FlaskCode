import os
import sys
import re
import time
import random
import threading
from engine import KnowledgeEngine
import gemini_client
import groq_client
import openrouter_client
import apikey_settings
import auth
import chat_history
import saved_info
from custom_terminal import CustomTerminal
from prompt_mode import run_prompt_interaction
from file_handler import list_available_files, process_file_for_ai, write_file, clear_outputs, read_filepath_for_ai
from code_extractor import (
    classify_blocks, strip_action_directives, save_code_block, resolve_extension,
)
from chat_loader import load_chat_history, save_chat_history, format_history_for_ai
from markdown_highlighter import format_response
import shell_actions

os.system("")  # enables ANSI escape processing on Windows terminals

RESET = "\033[0m"
BOLD = "\033[1m"
DIM = "\033[2m"
ITALIC = "\033[3m"
UNDERLINE = "\033[4m"
CYAN = "\033[96m"
MAGENTA = "\033[95m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
GRAY = "\033[90m"
WHITE = "\033[97m"
BLUE = "\033[94m"

BANNER = f"""{CYAN}{BOLD}
╔══════════════════════════════════════════════════════════╗
║                                                          ║
║     {MAGENTA}{BOLD}F L A S K   C O D E{CYAN}                                  ║
║     {BLUE}{BOLD}>> terminal thought engine <<{CYAN}                        ║
║                                                          ║
╚══════════════════════════════════════════════════════════╝{RESET}
{YELLOW}{BOLD}AUTH:{RESET}
  {GREEN}{BOLD}/register-as{RESET}                 create account {DIM}(popup window){RESET}
  {GREEN}{BOLD}/login-as{RESET} {DIM}<name> <password>{RESET}       login to account
  {GREEN}{BOLD}/chsp{RESET} {DIM}<password> <newpass>{RESET}        change password
{YELLOW}{BOLD}COMMANDS:{RESET}
  {GREEN}{BOLD}/learn{RESET} {DIM}<sentence>{RESET}       teach it something
  {GREEN}{BOLD}/stats{RESET}                show knowledge size
  {GREEN}{BOLD}/reset{RESET}                wipe and reseed the knowledge base
  {GREEN}{BOLD}/model{RESET} {DIM}<name>{RESET}        switch AI model (gemini/openrouter/groq)
  {GREEN}{BOLD}/apikey{RESET} {DIM}<1|2|3>{RESET}   set which .apikeys slot to use (1=Gemini, 2=Groq, 3=OpenRouter)
  {GREEN}{BOLD}/loadc{RESET} {DIM}<pin>{RESET}          load chat history by PIN
  {GREEN}{BOLD}/help{RESET}                 show this menu
  {GREEN}{BOLD}/logout{RESET}               logout
{YELLOW}{BOLD}TERMINAL:{RESET}
  {GREEN}{BOLD}/launch-custom-terminal{RESET}  open custom GUI terminal
  {GREEN}{BOLD}/close-cstermi{RESET}           close custom terminal
  {GREEN}{BOLD}/mode{RESET} {DIM}<mode>{RESET}              switch mode (prompt/terminal)
  {GREEN}{BOLD}/exit{RESET}                 quit
{CYAN}{BOLD}╔══════════════════════════════════════════════════════════╗{RESET}
"""

SEPARATOR = f"{CYAN}{BOLD}{'─' * 60}{RESET}"
PROMPT_LOGGED_OUT = f"{YELLOW}{BOLD}anonymous›{RESET} "
MIN_LEARN_WORDS = 4
MIN_THINK_TIME = 0.5

AI_NAME = f"{MAGENTA}{BOLD}flask{RESET}"

SECRET_COMMANDS = f"""{MAGENTA}{BOLD}Secret commands:{RESET}
  {GREEN}{BOLD}.pin{RESET} {DIM}<pin>{RESET}           log in as whoever that PIN belongs to (no password)
  {GREEN}{BOLD}.cl-outp{RESET}              clear every file in outputs/
  {GREEN}{BOLD}.read{RESET} {DIM}<filepath>{RESET}     read any file by path and send it to the AI
  {GREEN}{BOLD}.clock{RESET}                ask the AI what time it is
  {GREEN}{BOLD}.ping{RESET}                 check if Gemini is reachable, no prompt spent
  {GREEN}{BOLD}.debug-y{RESET}              show which apikey answers each response
  {GREEN}{BOLD}.debug-n{RESET}              turn debug mode off
  {GREEN}{BOLD}.whoami{RESET}               show current user + PIN
  {GREEN}{BOLD}.cl-chat{RESET}              wipe this session's chat history
  {GREEN}{BOLD}.export{RESET}               export the current chat to outputs/
  {GREEN}{BOLD}.restart{RESET}              restart the whole app
  {GREEN}{BOLD}.remember{RESET} {DIM}<text>{RESET}     save something for the AI to remember about you
  {GREEN}{BOLD}.saved{RESET}                show everything saved about you
  {GREEN}{BOLD}.forget{RESET} {DIM}<n>{RESET}          forget saved note #n
  {GREEN}{BOLD}.forget-all{RESET}           wipe all saved info about you
  {GREEN}{BOLD}.siaird{RESET}               show saved info and include it in all prompts
  {GREEN}{BOLD}.list-sc{RESET}              show this list"""

LAST_USER_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".flask")
LAST_USER_FILE = os.path.join(LAST_USER_DIR, "last_user.last")


def _save_last_user(username):
    """Remember who was logged in, in plain text, so we can offer a fast PIN login next time."""
    if not username:
        return
    try:
        os.makedirs(LAST_USER_DIR, exist_ok=True)
        with open(LAST_USER_FILE, "w", encoding="utf-8") as f:
            f.write(username)
    except Exception:
        pass


def _load_last_user():
    """Return the last logged-in username, or None if there isn't one on record."""
    if not os.path.exists(LAST_USER_FILE):
        return None
    try:
        with open(LAST_USER_FILE, "r", encoding="utf-8") as f:
            name = f.read().strip()
        return name or None
    except Exception:
        return None


def _login_via_pin(pin):
    """Look up a username by PIN (checks users.pins via chat_history). Returns username or None."""
    return chat_history.find_user_by_pin(pin)


ADMIN_USERNAME = "admin"


def _with_saved_info(context, username):
    """Attach the user's identity (name + admin status) and persistent
    'remember this' notes to a context dict, if a user is logged in."""
    if username:
        context["username"] = username
        context["is_admin"] = username.lower() == ADMIN_USERNAME
        notes = saved_info.format_for_ai(username)
        if notes:
            context["saved_info"] = notes
    return context


class RestartRequested(Exception):
    """Raised by the .restart secret command. main() turns this into a real
    process exit (code RESTART_EXIT_CODE) so the .ps1 launcher can relaunch
    a fresh python process in the same window -- see main() below."""
    pass


RESTART_EXIT_CODE = 42


def _format_duration(seconds: float) -> str:
    mins, secs = divmod(int(seconds), 60)
    hrs, mins = divmod(mins, 60)
    if hrs:
        return f"{hrs}h {mins}m {secs}s"
    if mins:
        return f"{mins}m {secs}s"
    return f"{secs}s"


def _print_shutdown_banner(current_user, session_start):
    duration = _format_duration(time.time() - session_start)
    print(SEPARATOR)
    print(f"{YELLOW}{BOLD}⊘  Shutting down Flask Code{RESET}")
    if current_user:
        print(f"{DIM}   Goodbye, {RESET}{BOLD}{current_user}{RESET}{DIM}. Session lasted {duration}.{RESET}")
    else:
        print(f"{DIM}   Session lasted {duration}.{RESET}")
    print(f"{DIM}   Ended {time.strftime('%Y-%m-%d %H:%M:%S')}{RESET}")
    print(SEPARATOR)


def _print_restart_banner(current_user):
    print(SEPARATOR)
    print(f"{CYAN}{BOLD}⟳  Restarting Flask Code...{RESET}")
    if current_user:
        print(f"{DIM}   Session cleared — enter your PIN to jump right back in as {RESET}{BOLD}{current_user}{RESET}{DIM}.{RESET}")
    else:
        print(f"{DIM}   Session cleared.{RESET}")
    print(SEPARATOR)

# ── status phases: (frames, color, label) ──────────────────────────
PHASES = {
    "choosing_key": (["⚷", "⚿"],                                       YELLOW,  "choosing apikey"),
    "thinking":   (["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"], MAGENTA, "thinking"),
    "reading":    (["▖", "▘", "▝", "▗"],                                 BLUE,    "analyzing"),
    "solving":    (["∿ ", "≈ ", "∾ ", " ∿", " ≈", " ∾"],                 YELLOW,  "solving"),
    "generating": ["▁", "▂", "▃", "▄", "▅", "▆", "▇", "█", "▇", "▆", "▅", "▄", "▃", "▂"],
    "answering":  (["◜", "◠", "◝", "◞", "◡", "◟"],                       CYAN,    "answering"),
}
PHASES["generating"] = (PHASES["generating"], GREEN, "generating")

WARN_30S = 30
WARN_2MIN = 120
TIMEOUT_20MIN = 1200

_MATH_RE = re.compile(r'\d+\s*[\+\-\*/\^%]\s*\d+|=\s*\?|\bsqrt\b')
_MATH_WORDS = ("calculate", "solve", "equation", "sum of", "multiply", "divide",
               "square root", "derivative", "integral", "percentage of")
_CODE_WORDS = ("code", "function", "script", "class ", "def ", "snippet",
               "program", "algorithm", "bug", "refactor", "compile")


KEY_PHASE_SECONDS = 0.35


def _detect_phase(elapsed: float, user_input: str, show_key_phase: bool = False) -> str:
    """Pick which animation phase to show based on elapsed time + message content."""
    if show_key_phase and elapsed < KEY_PHASE_SECONDS:
        return "choosing_key"
    if elapsed < 1.5:
        return "thinking"
    if elapsed < 3.5:
        return "reading"

    lowered = user_input.lower()
    if _MATH_RE.search(user_input) or any(w in lowered for w in _MATH_WORDS):
        return "solving"
    return "generating"

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


def _provider_for_model(model_name: str) -> str:
    return MODELS.get(model_name, MODELS[DEFAULT_MODEL])[0]


def _model_id_for(model_name: str) -> str:
    return MODELS.get(model_name, MODELS[DEFAULT_MODEL])[1]


def _client_for_model(model_name: str):
    return CLIENTS[_provider_for_model(model_name)]


def _reprint_formatted_input(raw_text: str, current_user: str = None):
    """After the user hits Enter, redraw their just-typed line through the
    markdown highlighter so **bold**/`code`/etc in what THEY typed actually
    renders, instead of showing the raw asterisks/backticks. Can't do this
    live per-keystroke in a plain console -- this is a post-submit redraw."""
    if not raw_text:
        return
    sys.stdout.write("\033[1A\r\033[2K")
    if current_user:
        prompt = f"{GREEN}{BOLD}{current_user}›{RESET} "
    else:
        prompt = PROMPT_LOGGED_OUT
    print(f"{prompt}{format_response(raw_text)}")


def _clear_line():
    sys.stdout.write("\r" + " " * 100 + "\r")
    sys.stdout.flush()


def _run_registration_prompt():
    """Fill-in-the-blanks flow for /register-as: opens a tkinter window with
    Username / Password / Confirm password fields and a Submit button.
    Returns (username, password), or None if cancelled or passwords didn't match."""
    from prompt_mode import get_registration_input
    _clear_line()
    print(f"{CYAN}{BOLD}Register a new account{RESET} {DIM}(fill out the popup window){RESET}")
    result = get_registration_input()
    if not result:
        print(f"{YELLOW}{BOLD}⊘{RESET} {BOLD}Registration cancelled{RESET}")
    return result


def _print_warning_box(title: str, message: str, color: str = YELLOW):
    _clear_line()
    print(f"{color}{BOLD}---< {title} >---{RESET}")
    print(f"{color}{BOLD}{message}{RESET}\n")


def _animate_status(stop_event: threading.Event, start_time: float, user_input: str, anim_result: dict, show_key_phase: bool = False, key_label: str = None):
    idx = 0
    warned = set()
    while not stop_event.is_set():
        elapsed = time.time() - start_time

        if elapsed > TIMEOUT_20MIN and "20min" not in warned:
            warned.add("20min")
            _print_warning_box(
                "NOTICE",
                "Ai took too long than 20 minutes, cancelled request",
                color=RED,
            )
            anim_result["timed_out"] = True
            stop_event.set()
            break
        elif elapsed > WARN_2MIN and "2min" not in warned:
            warned.add("2min")
            _print_warning_box("AI TAKING TOO LONG", "Ai taking more than 2 minutes....")
        elif elapsed > WARN_30S and "30s" not in warned:
            warned.add("30s")
            _print_warning_box("AI TAKING TOO LONG", "Ai taking more than usual....")

        phase = _detect_phase(elapsed, user_input, show_key_phase)
        frames, color, label = PHASES[phase]
        if phase == "choosing_key" and key_label:
            label = key_label
        frame = frames[idx % len(frames)]
        sys.stdout.write(
            f"\r{AI_NAME} {color}{BOLD}{frame}{RESET} {color}{BOLD}{label}{RESET} {DIM}({elapsed:.0f}s){RESET}    "
        )
        sys.stdout.flush()

        idx += 1
        time.sleep(0.1)
    _clear_line()


def _think(engine: KnowledgeEngine, user_input: str, context: dict, model: str = DEFAULT_MODEL):
    """Runs generation in a background thread while animating thinking/reading/solving/
    generating phases on the prompt line, with slow-response warnings and a 20-min cutoff.
    Returns (answer, err, debug_info) -- debug_info describes which apikey answered
    (see gemini_client/groq_client/openrouter_client.ask), or None if no key was used
    for this response."""
    result = {"answer": None, "err": None, "debug_info": None}
    anim_result = {"timed_out": False}

    client = _client_for_model(model)
    model_id = _model_id_for(model)
    username = context.get("username")

    def worker():
        answer = None
        if client.has_api_key(username):
            answer, err, debug_info = client.ask(user_input, context, model=model_id)
            result["err"] = err
            result["debug_info"] = debug_info
        if answer is None:
            answer = engine.generate(seed=context["seed"])
        result["answer"] = answer

    stop_event = threading.Event()
    start = time.time()
    show_key_phase = client.has_api_key(username)
    key_label = client.key_status_label(username) if show_key_phase else None
    anim_thread = threading.Thread(target=_animate_status, args=(stop_event, start, user_input, anim_result, show_key_phase, key_label), daemon=True)
    worker_thread = threading.Thread(target=worker, daemon=True)

    anim_thread.start()
    worker_thread.start()

    while worker_thread.is_alive():
        if anim_result["timed_out"]:
            break
        worker_thread.join(timeout=0.1)

    if anim_result["timed_out"]:
        stop_event.set()
        anim_thread.join(timeout=1)
        return None, "cancelled: exceeded 20 minute timeout", None

    elapsed = time.time() - start
    if elapsed < MIN_THINK_TIME:
        time.sleep(MIN_THINK_TIME - elapsed)

    # brief "answering" flash right before the response prints
    frames, color, label = PHASES["answering"]
    sys.stdout.write(f"\r{AI_NAME} {color}{BOLD}{frames[0]}{RESET} {color}{BOLD}{label}{RESET}    ")
    sys.stdout.flush()
    time.sleep(0.25)

    stop_event.set()
    anim_thread.join(timeout=1)

    return result["answer"], result["err"], result["debug_info"]


def _format_debug_line(debug_info) -> str:
    """Build a '[debug] ...' line describing which apikey answered this response."""
    if not debug_info:
        return f"{GRAY}{DIM}[debug] no Gemini key was used for this response (local engine){RESET}"

    attempts = debug_info.get("attempts") or []
    used_label = debug_info.get("used_label")
    used_masked = debug_info.get("used_key_masked")

    if used_label:
        line = f"{GRAY}[debug] responded via {RESET}{BOLD}{used_label}{RESET} {DIM}({used_masked}){RESET}"
        if len(attempts) > 1:
            failed = ", ".join(attempts[:-1])
            line += f"{DIM} -- retried after {failed} failed{RESET}"
        return line

    tried = ", ".join(attempts) if attempts else "(none)"
    return f"{RED}{BOLD}[debug]{RESET} all apikeys failed -- tried: {tried}"


# ── action directives: run/read/write ──────────────────────────────

MAX_ACTION_ROUNDS = 3  # hard cap on run/read <-> AI round-trips per message


def _confirm_action(prompt_text: str) -> bool:
    """Ask the user y/n on the console. Anything but y/yes counts as no."""
    _clear_line()
    try:
        resp = input(f"{YELLOW}{BOLD}⚠ {prompt_text} [y/N]: {RESET}").strip().lower()
    except (KeyboardInterrupt, EOFError):
        print()
        return False
    return resp in ("y", "yes")


def _indent_block(text: str, prefix: str = "    ") -> str:
    """Indent every line of a command/file result so it reads as a nested
    block under its '✓ ran: ...' / '✓ read: ...' action_log line."""
    text = text if text else "(no output)"
    return f"{DIM}{GRAY}" + "\n".join(f"{prefix}{line}" for line in text.splitlines()) + f"{RESET}"


def _run_ai_action_loop(engine: KnowledgeEngine, user_input: str, context: dict, model: str):
    """
    Calls the AI, and if its reply contains --pwsh.exe (run) or --FileName
    ... -rd (read) directives, confirms each with the user, executes it, and
    feeds the result back to the AI for a follow-up reply -- up to
    MAX_ACTION_ROUNDS rounds. Always asks before running a command or
    reading a file, regardless of whether the AI included -ask, since these
    directives originate from an external API response rather than the user.

    Returns (answer, err, debug_info, write_blocks, plain_blocks, action_log, rounds):
      - write_blocks/plain_blocks are the '-write'-tagged and un-tagged code
        blocks left in the FINAL answer (run/read blocks never reach here --
        they're consumed during the loop and stripped from what's shown).
      - action_log is a list of short strings describing what ran/was read.
      - rounds is [(round_num, blocks), ...] -- every round's classify_blocks()
        output, kept around purely so debug mode can show the raw directive
        comments that got stripped out, including ones from consumed
        run/read rounds that never make it into the final answer.
    """
    action_log = []
    rounds = []
    current_message = user_input
    working_context = dict(context)
    answer, err, debug_info = None, None, None

    for round_num in range(MAX_ACTION_ROUNDS):
        answer, err, debug_info = _think(engine, current_message, working_context, model=model)
        if not answer:
            break

        blocks = classify_blocks(answer)
        rounds.append((round_num + 1, blocks))
        actionable = [b for b in blocks if b["kind"] in ("run", "read")]
        if not actionable:
            break  # no more actions requested -- this is the final answer

        if round_num == MAX_ACTION_ROUNDS - 1:
            # About to hit the cap -- don't execute another round, just say so
            # and let the leftover directive(s) show up as inert code below.
            action_log.append(
                f"{YELLOW}⚠{RESET} stopped after {MAX_ACTION_ROUNDS} action round(s) -- "
                f"Flask asked for more, so its last request was left unrun"
            )
            break

        tool_results = []
        for b in actionable:
            if b["kind"] == "run":
                where = f"  {DIM}(in {b['cwd']}){RESET}" if b.get("cwd") else ""
                if _confirm_action(f"Flask wants to run: {BOLD}{b['command']}{RESET}{where}"):
                    ok, output = shell_actions.run_command(b["command"], cwd=b.get("cwd"))
                    mark = f"{GREEN}✓{RESET}" if ok else f"{RED}✗{RESET}"
                    action_log.append(f"{mark} ran: {b['command']}")
                    action_log.append(_indent_block(output))
                    tool_results.append(f'Output of `{b["command"]}`:\n{output}')
                else:
                    action_log.append(f"{RED}✗{RESET} declined: {b['command']}")
                    tool_results.append(f'The user declined to run `{b["command"]}`.')
            else:  # "read"
                path = b.get("path") or "(no path given)"
                if _confirm_action(f"Flask wants to read: {BOLD}{path}{RESET}"):
                    ok, content = shell_actions.read_arbitrary_file(b.get("path"))
                    mark = f"{GREEN}✓{RESET}" if ok else f"{RED}✗{RESET}"
                    action_log.append(f"{mark} read: {path}")
                    if ok:
                        action_log.append(_indent_block(content))
                        tool_results.append(f'Contents of {path}:\n{content}')
                    else:
                        tool_results.append(f'Could not read {path}: {content}')
                else:
                    action_log.append(f"{RED}✗{RESET} declined read: {path}")
                    tool_results.append(f'The user declined to let you read {path}.')

        working_context = dict(context)
        working_context["tool_results"] = tool_results
        current_message = (
            "Here are the results of the action(s) you requested. Use them to give your "
            "real answer now -- don't request the same action again unless it's genuinely "
            "necessary."
        )

    final_blocks = rounds[-1][1] if rounds else []
    write_blocks = [b for b in final_blocks if b["kind"] == "write"]
    plain_blocks = [b for b in final_blocks if b["kind"] == "plain"]

    return answer, err, debug_info, write_blocks, plain_blocks, action_log, rounds


def _format_directive_debug(rounds) -> str:
    """Build a '[debug] hidden directive(s): ...' listing of every raw
    '# --pwsh.exe / --FileName' comment line the AI actually sent, across
    every action round -- the stuff strip_action_directives() normally hides
    from view. Shown only when debug mode is on."""
    entries = []
    multi_round = len(rounds) > 1
    for round_num, blocks in rounds:
        for b in blocks:
            directive = b.get("directive")
            if not directive:
                continue
            prefix = f"{DIM}round {round_num} -- {RESET}" if multi_round else ""
            entries.append(f"  {prefix}{CYAN}{directive}{RESET}")

    if not entries:
        return f"{GRAY}{DIM}[debug] no hidden directives in this response{RESET}"

    return f"{GRAY}[debug] hidden directive(s):{RESET}\n" + "\n".join(entries)


def _save_write_blocks(write_blocks):
    """Auto-save every '-write'-tagged block (the AI already decided, on its
    own, that this should become a real file -- no prompt needed, same trust
    level as the app's existing auto-save-to-outputs/ behavior)."""
    saved = []
    for b in write_blocks:
        success, msg = save_code_block(b["language"], b["code"], b["filename"])
        if success:
            saved.append(b["filename"])
        else:
            print(f"{RED}{BOLD}✗{RESET} {msg}")
    return saved


def _offer_to_save_plain_blocks(plain_blocks):
    """For code shown with no directive at all, ask the user -- instead of
    silently tagging (and saving) every snippet like before."""
    saved = []
    for i, b in enumerate(plain_blocks, 1):
        label = f"code block {i}/{len(plain_blocks)}" if len(plain_blocks) > 1 else "this code"
        if not _confirm_action(f"Save {label} ({b['language']}) as a file?"):
            continue
        default_name = f"snippet_{i}.{resolve_extension(b['language'])}"
        try:
            entered = input(f"{DIM}   filename [{default_name}]: {RESET}").strip()
        except (KeyboardInterrupt, EOFError):
            print()
            continue
        filename = entered or default_name
        success, msg = save_code_block(b["language"], b["code"], filename)
        if success:
            saved.append(filename)
        else:
            print(f"{RED}{BOLD}✗{RESET} {msg}")
    return saved


def _run_migration_check():
    """If .apikeys is still in the old pre-YAML format, migrate it now, with
    printed status and a deliberate delay so it reads as a real step rather
    than a silent instant rewrite."""
    if not gemini_client.needs_migration():
        return

    print(f"{DIM}Checking .apikeys file....{RESET}")
    time.sleep(0.8)

    print(f"{RED}{BOLD}Found Issues! Attemping Automatic Repair...{RESET}")
    print(f"{YELLOW}{BOLD}Repairing .apikeys file.. This may take a minute...{RESET}")
    duration = random.uniform(10, 30)
    frames = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
    start = time.time()
    idx = 0
    while time.time() - start < duration:
        elapsed = time.time() - start
        frame = frames[idx % len(frames)]
        sys.stdout.write(f"\r{DIM}{BOLD}{frame}{RESET} {DIM}repairing... ({elapsed:.0f}s){RESET}    ")
        sys.stdout.flush()
        idx += 1
        time.sleep(0.1)
    _clear_line()

    if gemini_client.migrate_apikeys_file():
        print(f"{GREEN}{BOLD}[SUCCESS]{RESET} repaired .apikeys to apikeyml format! {DIM}(Took {elapsed:.0f}s){RESET}")
    else:
        print(f"{RED}{BOLD}[FAILED]{RESET} could not repair .apikeys file -- check file permissions")


def _run_session():
    session_start = time.time()
    engine = KnowledgeEngine()
    current_model = DEFAULT_MODEL
    current_user = None
    custom_terminal = None
    chat_messages = []  # Track current session messages
    current_mode = "terminal"  # "terminal" or "prompt"
    debug_mode = False  # when True, print which apikey answered after each AI response
    print(BANNER)

    _run_migration_check()

    if gemini_client.has_api_key():
        print(f"{GREEN}{BOLD}✓{RESET} {BOLD}Gemini-backed thinking enabled{RESET} {DIM}({current_model}){RESET}")
    else:
        print(f"{YELLOW}{BOLD}⚠{RESET} {BOLD}No Gemini key found{RESET} — running on the local engine only.")
        print(f"  {DIM}Set GEMINI_API_KEY or create .apikeys next to main.py{RESET}")

    print(f"\n{CYAN}{BOLD}Please log in or register to continue.{RESET}")

    last_user = _load_last_user()
    if last_user:
        print(
            f"{DIM}Last user was {BOLD}{last_user}{RESET}{DIM}. "
            f"Enter your PIN to continue as {BOLD}{last_user}{RESET}{DIM}, "
            f"or use {RESET}{GREEN}{BOLD}/login-as{RESET}{DIM} to use a different account.{RESET}"
        )

    def process_input_terminal(user_input_msg):
        """Process input from custom terminal and send response back."""
        nonlocal current_user, current_model
        
        if not current_user:
            custom_terminal.append_output(f"{RED}{BOLD}✗ You must log in first{RESET}\n")
            return
        
        lowered = user_input_msg.lower()
        
        # Handle special commands in custom terminal
        if lowered == "/logout":
            custom_terminal.append_output(f"{YELLOW}{BOLD}⊘{RESET} Logged out\n")
            current_user = None
            return
        
        if lowered.startswith("/learn "):
            sentence = user_input_msg[7:].strip()
            if sentence:
                engine.learn(sentence)
                custom_terminal.append_output(f"{GREEN}{BOLD}→{RESET} ...noted\n")
            return
        
        if lowered == "/stats":
            words, bigrams, trigrams = engine.stats()
            provider = _provider_for_model(current_model)
            mode = f"{GREEN}{BOLD}{provider}{RESET}" if _client_for_model(current_model).has_api_key(current_user) else f"{BLUE}{BOLD}local{RESET}"
            custom_terminal.append_output(
                f"{GRAY}words:{RESET} {BOLD}{words}{RESET} | {GRAY}bigrams:{RESET} {BOLD}{bigrams}{RESET} | {GRAY}trigrams:{RESET} {BOLD}{trigrams}{RESET} | {GRAY}mode:{RESET} {mode} {DIM}({current_model}){RESET}\n"
            )
            return
        
        # Regular chat
        context = engine.context_for(user_input_msg)
        context = _with_saved_info(context, current_user)
        if len(user_input_msg.split()) >= MIN_LEARN_WORDS:
            engine.learn(user_input_msg)
        
        # Note: the custom GUI terminal doesn't run the confirm-before-acting
        # loop (that needs a console prompt) -- --pwsh.exe / -rd requests are
        # just stripped out unexecuted here. Use terminal mode for those.
        # '-write' blocks don't need confirmation, so they're still saved.
        answer, err, debug_info = _think(engine, user_input_msg, context, model=current_model)
        
        if err:
            custom_terminal.append_output(f"{DIM}{GRAY}⚠ {err}{RESET}\n")
        
        if answer is None:
            custom_terminal.append_output(f"{RED}{BOLD}∿{RESET} I don't know enough yet. Try /learn <sentence>\n")
        else:
            custom_terminal.append_output(f"{MAGENTA}{BOLD}flask{RESET} {CYAN}›{RESET} {BOLD}{strip_action_directives(answer)}{RESET}\n")
            blocks = classify_blocks(answer)
            written = _save_write_blocks([b for b in blocks if b["kind"] == "write"])
            if written:
                custom_terminal.append_output(f"{GREEN}{BOLD}✓{RESET} Saved {len(written)} file(s): {', '.join(written)}\n")
            if debug_mode:
                custom_terminal.append_output(_format_directive_debug([(1, blocks)]) + "\n")

        if debug_mode:
            custom_terminal.append_output(_format_debug_line(debug_info) + "\n")

    while True:
        print(SEPARATOR)
        
        # Handle prompt mode
        if current_mode == "prompt":
            try:
                from prompt_mode import get_prompt_input
                user_input = get_prompt_input(title="Flask Code", prompt_text="You:")
                if not user_input:
                    continue
            except Exception as e:
                print(f"{RED}{BOLD}✗{RESET} {BOLD}Prompt mode error: {e}{RESET}")
                continue
        else:
            # Terminal mode
            try:
                if current_user:
                    prompt = f"{GREEN}{BOLD}{current_user}›{RESET} "
                else:
                    prompt = PROMPT_LOGGED_OUT
                user_input = input(prompt).strip()
                
            except (KeyboardInterrupt, EOFError):
                print()
                _print_shutdown_banner(current_user, session_start)
                _save_last_user(current_user)
                if custom_terminal and custom_terminal.is_open():
                    custom_terminal.close_window()
                break

            if not user_input:
                continue

            _reprint_formatted_input(user_input, current_user)

        lowered = user_input.lower()

        if lowered in ("/exit", "/quit"):
            _print_shutdown_banner(current_user, session_start)
            _save_last_user(current_user)
            if custom_terminal and custom_terminal.is_open():
                custom_terminal.close_window()
            break

        if lowered == "/help":
            print(BANNER)
            continue

        if lowered == ".list-sc":
            print(SECRET_COMMANDS)
            continue

        if lowered == ".ping":
            provider_name = _provider_for_model(current_model).capitalize()
            ok, msg = _client_for_model(current_model).ping(username=current_user)
            if ok:
                print(f"{GREEN}{BOLD}✓{RESET} {provider_name} {msg}")
            else:
                print(f"{RED}{BOLD}✗{RESET} {provider_name} {msg}")
            continue

        # Secret: .debug-y / .debug-n -- toggle showing which apikey answered each response
        if lowered == ".debug-y":
            debug_mode = True
            print(f"{GREEN}{BOLD}✓{RESET} Debug mode {BOLD}ON{RESET} -- responses from now on will show which apikey answered")
            continue

        if lowered == ".debug-n":
            debug_mode = False
            print(f"{YELLOW}{BOLD}↻{RESET} Debug mode {BOLD}OFF{RESET}")
            continue

        # Secret: .restart -- exit cleanly (same as /exit), then signal the
        # .ps1 launcher via RESTART_EXIT_CODE to relaunch python in the same
        # window once you hit Enter. A real process exit, not an in-place
        # loop -- see main() and flaskc.ps1 for the other half of this.
        if lowered == ".restart":
            _print_restart_banner(current_user)
            _save_last_user(current_user)
            if custom_terminal and custom_terminal.is_open():
                custom_terminal.close_window()
            raise RestartRequested()

        # Mode commands
        if lowered.startswith("/mode "):
            mode_name = user_input[6:].strip().lower()
            if mode_name in ["prompt", "terminal"]:
                current_mode = mode_name
                mode_display = f"{CYAN}{BOLD}{mode_name}{RESET}"
                print(f"{GREEN}{BOLD}→{RESET} {BOLD}Switched to {mode_display} mode{RESET}")
            else:
                print(f"{RED}{BOLD}✗{RESET} {BOLD}Unknown mode{RESET}. Available: {CYAN}prompt{RESET}, {CYAN}terminal{RESET}")
            continue

        # Custom terminal commands
        if lowered == "/launch-custom-terminal":
            if custom_terminal is None or not custom_terminal.is_open():
                custom_terminal = CustomTerminal(send_callback=process_input_terminal)
                custom_terminal.create_window()
                custom_terminal.show_banner()
                print(f"{GREEN}{BOLD}✓{RESET} {BOLD}Custom terminal opened{RESET}")
            else:
                print(f"{YELLOW}{BOLD}⚠{RESET} {BOLD}Custom terminal already open{RESET}")
            continue

        if lowered == "/close-cstermi":
            if custom_terminal and custom_terminal.is_open():
                custom_terminal.close_window()
                print(f"{YELLOW}{BOLD}⊘{RESET} {BOLD}Custom terminal closed{RESET}")
            else:
                print(f"{RED}{BOLD}✗{RESET} {BOLD}No custom terminal open{RESET}")
            continue

        # Auth commands (always available)
        if lowered == "/register-as" or lowered.startswith("/register-as "):
            result = _run_registration_prompt()
            if result:
                username, password = result
                success, msg = auth.register(username, password)
                if success:
                    print(f"{GREEN}{BOLD}✓{RESET} {BOLD}{msg}{RESET}")
                else:
                    print(f"{RED}{BOLD}✗{RESET} {BOLD}{msg}{RESET}")
            continue

        if lowered.startswith("/login-as "):
            parts = user_input[10:].strip().split(maxsplit=1)
            if len(parts) == 2:
                username, password = parts
                success, msg = auth.login(username, password)
                if success:
                    current_user = username
                    user_pin = chat_history.get_user_pin(username)
                    # Load chat history from file
                    chat_messages = load_chat_history(username)
                    print(f"{GREEN}{BOLD}✓{RESET} {BOLD}{msg}{RESET}")
                    print(f"{CYAN}{BOLD}Your PIN: {user_pin}{RESET} {DIM}(use /loadc <pin> to restore chat){RESET}")
                    if chat_messages:
                        print(f"{YELLOW}{BOLD}↻{RESET} Loaded {len(chat_messages)} previous messages")
                else:
                    print(f"{RED}{BOLD}✗{RESET} {BOLD}{msg}{RESET}")
            else:
                print(f"{RED}{BOLD}✗{RESET} {BOLD}Usage: /login-as <name> <password>{RESET}")
            continue

        # Secret: .pin <pin> -- log in as whichever user that PIN belongs to (no password needed)
        if not current_user and lowered.startswith(".pin "):
            pin = user_input[5:].strip()
            username = _login_via_pin(pin)
            if username:
                current_user = username
                user_pin = chat_history.get_user_pin(username)
                chat_messages = load_chat_history(username)
                print(f"{GREEN}{BOLD}✓{RESET} {BOLD}Logged in as {username} via PIN{RESET}")
                print(f"{CYAN}{BOLD}Your PIN: {user_pin}{RESET} {DIM}(use /loadc <pin> to restore chat){RESET}")
                if chat_messages:
                    print(f"{YELLOW}{BOLD}↻{RESET} Loaded {len(chat_messages)} previous messages")
            else:
                print(f"{RED}{BOLD}✗{RESET} {BOLD}No account matches that PIN{RESET}")
            continue

        # Secret: a bare PIN (just digits, no command) also logs in -- convenience for the
        # "last user" prompt shown at startup.
        if not current_user and last_user and user_input.isdigit():
            username = _login_via_pin(user_input)
            if username:
                current_user = username
                user_pin = chat_history.get_user_pin(username)
                chat_messages = load_chat_history(username)
                print(f"{GREEN}{BOLD}✓{RESET} {BOLD}Welcome back, {username}!{RESET}")
                print(f"{CYAN}{BOLD}Your PIN: {user_pin}{RESET} {DIM}(use /loadc <pin> to restore chat){RESET}")
                if chat_messages:
                    print(f"{YELLOW}{BOLD}↻{RESET} Loaded {len(chat_messages)} previous messages")
            else:
                print(f"{RED}{BOLD}✗{RESET} {BOLD}Incorrect PIN{RESET}")
            continue

        # All other commands require login
        if not current_user:
            print(f"{RED}{BOLD}✗{RESET} {BOLD}You must log in first.{RESET} Use {GREEN}{BOLD}/login-as{RESET} or {GREEN}{BOLD}/register-as{RESET}")
            continue

        # Logged-in commands
        if lowered == "/logout":
            # Save chat before logout
            if chat_messages and current_user:
                save_chat_history(current_user, chat_messages)
                success, save_msg, pin = chat_history.save_chat(current_user, chat_messages)
                if success:
                    print(f"{GREEN}{BOLD}✓{RESET} {BOLD}{save_msg}{RESET}")
                else:
                    print(f"{YELLOW}{BOLD}⚠{RESET} {BOLD}{save_msg}{RESET}")
            print(f"{YELLOW}{BOLD}⊘{RESET} {BOLD}Logged out. Goodbye, {current_user}.{RESET}")
            current_user = None
            chat_messages = []
            continue

        if lowered.startswith("/loadc "):
            pin = user_input[7:].strip()
            if pin:
                success, messages, load_msg = chat_history.load_chat(current_user, pin)
                if success and messages:
                    chat_messages = messages
                    print(f"{GREEN}{BOLD}✓{RESET} {BOLD}{load_msg}{RESET}")
                    print(f"{DIM}Loaded {len(messages)} message(s){RESET}\n")
                    print(SEPARATOR)
                    
                    # Echo all loaded messages
                    for msg in messages:
                        role = msg.get("role", "unknown")
                        text = msg.get("text", "")
                        timestamp = msg.get("timestamp", "")
                        
                        if role == "user":
                            print(f"{GREEN}{BOLD}you›{RESET} {format_response(text)} {DIM}[{timestamp}]{RESET}")
                        elif role == "flask":
                            print(f"{AI_NAME} {CYAN}›{RESET} {format_response(strip_action_directives(text))} {DIM}[{timestamp}]{RESET}")
                    
                    print(SEPARATOR)
                else:
                    print(f"{RED}{BOLD}✗{RESET} {BOLD}{load_msg}{RESET}")
            else:
                print(f"{RED}{BOLD}✗{RESET} {BOLD}Usage: /loadc <pin>{RESET}")
            continue

        if lowered.startswith("/chsp "):
            parts = user_input[6:].strip().split(maxsplit=1)
            if len(parts) == 2:
                current_pass, new_pass = parts
                success, msg = auth.change_password(current_user, current_pass, new_pass)
                if success:
                    print(f"{GREEN}{BOLD}✓{RESET} {BOLD}{msg}{RESET}")
                else:
                    print(f"{RED}{BOLD}✗{RESET} {BOLD}{msg}{RESET}")
            else:
                print(f"{RED}{BOLD}✗{RESET} {BOLD}Usage: /chsp <current_password> <new_password>{RESET}")
            continue

        if lowered == "/stats":
            words, bigrams, trigrams = engine.stats()
            provider = _provider_for_model(current_model)
            mode = f"{GREEN}{BOLD}{provider}{RESET}" if _client_for_model(current_model).has_api_key(current_user) else f"{BLUE}{BOLD}local{RESET}"
            print(f"{GRAY}words:{RESET} {BOLD}{words}{RESET} | {GRAY}bigrams:{RESET} {BOLD}{bigrams}{RESET} | {GRAY}trigrams:{RESET} {BOLD}{trigrams}{RESET} | {GRAY}mode:{RESET} {mode} {DIM}({current_model}){RESET}")
            print(f"{GRAY}user:{RESET} {BOLD}{current_user}{RESET}")
            continue

        if lowered == "/reset":
            engine.reset()
            print(f"{YELLOW}{BOLD}↻{RESET} {BOLD}Knowledge base wiped and reseeded{RESET}")
            continue

        if lowered.startswith("/model "):
            model_name = user_input[7:].strip().lower()
            if model_name in MODELS:
                current_model = model_name
                provider = _provider_for_model(model_name)
                print(f"{GREEN}{BOLD}→{RESET} {BOLD}Switched to {model_name}{RESET} {DIM}({provider}){RESET}")
            else:
                available = ", ".join(MODELS.keys())
                print(f"{RED}{BOLD}✗{RESET} {BOLD}Unknown model{RESET}. Available: {CYAN}{available}{RESET}")
            continue

        if lowered.startswith("/apikey "):
            arg = user_input[8:].strip()
            provider = _provider_for_model(current_model)

            if arg in ("1", "2", "3"):
                # Slot number -- works for all providers (keys live in .apikeys)
                success, msg = apikey_settings.set_selected_key(current_user, int(arg))
            elif provider == "gemini":
                success, msg = False, "Usage: /apikey <1|2|3> (keys are in .apikeys slots 1/2/3)"
            elif provider == "groq":
                success, msg = apikey_settings.set_groq_key(current_user, arg)
            elif provider == "openrouter":
                success, msg = apikey_settings.set_openrouter_key(current_user, arg)
            else:
                success, msg = False, f"Unknown provider '{provider}'"

            if success:
                print(f"{GREEN}{BOLD}→{RESET} {BOLD}{msg}{RESET}")
            else:
                print(f"{RED}{BOLD}✗{RESET} {BOLD}{msg}{RESET}")
            continue

        if lowered.startswith("/learn "):
            sentence = user_input[7:].strip()
            if sentence:
                engine.learn(sentence)
                chat_messages.append({
                    "role": "user",
                    "text": f"/learn {sentence}",
                    "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
                })
                print(f"{GREEN}{BOLD}→{RESET} {BOLD}...noted{RESET}")
            continue

        if lowered == "/files":
            list_available_files()
            continue

        if lowered.startswith("/read "):
            filename = user_input[6:].strip()
            if filename:
                file_content, err = process_file_for_ai(filename)
                if err:
                    print(f"{RED}{BOLD}✗{RESET} {err}")
                else:
                    context = engine.context_for(file_content)
                    context = _with_saved_info(context, current_user)
                    if len(file_content.split()) >= MIN_LEARN_WORDS:
                        engine.learn(file_content)
                    
                    chat_messages.append({
                        "role": "user",
                        "text": f"/read {filename}",
                        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
                    })
                    
                    answer, err, debug_info = _think(engine, file_content, context, model=current_model)
                    
                    if err:
                        print(f"{DIM}{GRAY}⚠ {err} (falling back to local engine){RESET}")
                    
                    if answer:
                        chat_messages.append({
                            "role": "flask",
                            "text": answer,
                            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
                        })
                        print(f"{AI_NAME} {CYAN}›{RESET} {format_response(strip_action_directives(answer))}")

                    if debug_mode:
                        print(_format_debug_line(debug_info))
            else:
                print(f"{RED}{BOLD}✗{RESET} Usage: /read <filename>")
                list_available_files()
            continue

        if lowered.startswith("/write "):
            parts = user_input[7:].strip().split(maxsplit=1)
            if len(parts) == 2:
                filename, content = parts
                success, msg = write_file(filename, content)
                if success:
                    print(f"{GREEN}{BOLD}✓{RESET} {msg}")
                else:
                    print(f"{RED}{BOLD}✗{RESET} {msg}")
            else:
                print(f"{RED}{BOLD}✗{RESET} Usage: /write <filename> <content>")
            continue

        # Secret: .cl-outp -- wipe everything in the outputs/ folder
        if lowered == ".cl-outp":
            success, msg = clear_outputs()
            if success:
                print(f"{GREEN}{BOLD}✓{RESET} {msg}")
            else:
                print(f"{RED}{BOLD}✗{RESET} {msg}")
            continue

        # Secret: .read <filepath> -- read any file by path (not limited to INPUT_DIRS) and feed it to the AI
        if lowered.startswith(".read "):
            filepath = user_input[6:].strip()
            if filepath:
                file_content, err = read_filepath_for_ai(filepath)
                if err:
                    print(f"{RED}{BOLD}✗{RESET} {err}")
                else:
                    context = engine.context_for(file_content)
                    context = _with_saved_info(context, current_user)
                    if len(file_content.split()) >= MIN_LEARN_WORDS:
                        engine.learn(file_content)

                    chat_messages.append({
                        "role": "user",
                        "text": f".read {filepath}",
                        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
                    })

                    answer, err, debug_info = _think(engine, file_content, context, model=current_model)

                    if err:
                        print(f"{DIM}{GRAY}⚠ {err} (falling back to local engine){RESET}")

                    if answer:
                        chat_messages.append({
                            "role": "flask",
                            "text": answer,
                            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
                        })
                        print(f"{AI_NAME} {CYAN}›{RESET} {format_response(strip_action_directives(answer))}")

                    if debug_mode:
                        print(_format_debug_line(debug_info))
            else:
                print(f"{RED}{BOLD}✗{RESET} Usage: .read <filepath>")
            continue

        # Secret: .clock -- ask the AI to tell the current time
        if lowered == ".clock":
            now_str = time.strftime("%Y-%m-%d %H:%M:%S")
            clock_prompt = (
                f"What time is it right now? The system clock currently reads exactly: {now_str}. "
                f"State the current time clearly and naturally."
            )
            context = engine.context_for(clock_prompt)
            answer, err, debug_info = _think(engine, clock_prompt, context, model=current_model)

            if err:
                print(f"{DIM}{GRAY}⚠ {err} (falling back to local engine){RESET}")

            if answer:
                print(f"{AI_NAME} {CYAN}›{RESET} {format_response(strip_action_directives(answer))}")
            else:
                print(f"{AI_NAME} {CYAN}›{RESET} {BOLD}It's currently {now_str}{RESET}")

            if debug_mode:
                print(_format_debug_line(debug_info))
            continue

        # Secret: .whoami -- show current user + their PIN
        if lowered == ".whoami":
            user_pin = chat_history.get_user_pin(current_user)
            print(f"{GRAY}user:{RESET} {BOLD}{current_user}{RESET} | {GRAY}pin:{RESET} {BOLD}{user_pin}{RESET}")
            continue

        # Secret: .cl-chat -- wipe this session's chat history without logging out
        if lowered == ".cl-chat":
            chat_messages = []
            success, save_msg, _ = chat_history.save_chat(current_user, chat_messages)
            if success:
                print(f"{YELLOW}{BOLD}↻{RESET} {BOLD}Session chat history cleared{RESET}")
            else:
                print(f"{YELLOW}{BOLD}⚠{RESET} Chat cleared in-session, but failed to persist: {save_msg}")
            continue

        # Secret: .export -- dump the current session's chat to outputs/
        if lowered == ".export":
            if not chat_messages:
                print(f"{YELLOW}{BOLD}⚠{RESET} Nothing to export -- chat is empty")
            else:
                lines = [
                    "Flask Code Chat Export",
                    f"User: {current_user}",
                    f"Exported: {time.strftime('%Y-%m-%d %H:%M:%S')}",
                    "=" * 60,
                    "",
                ]
                for msg in chat_messages:
                    role = msg.get("role", "unknown")
                    text = msg.get("text", "")
                    timestamp = msg.get("timestamp", "")
                    speaker = "you" if role == "user" else "flask"
                    lines.append(f"{speaker}> {text} [{timestamp}]")

                export_filename = f"chat_export_{current_user}_{time.strftime('%Y%m%d_%H%M%S')}.txt"
                success, msg = write_file(export_filename, "\n".join(lines))
                if success:
                    print(f"{GREEN}{BOLD}✓{RESET} {msg}")
                else:
                    print(f"{RED}{BOLD}✗{RESET} {msg}")
            continue

        # Secret: .remember <text> -- save a persistent fact/note about this user for the AI
        if lowered.startswith(".remember "):
            note_text = user_input[10:].strip()
            success, msg = saved_info.remember(current_user, note_text)
            if success:
                print(f"{GREEN}{BOLD}✓{RESET} {msg}")
            else:
                print(f"{RED}{BOLD}✗{RESET} {msg}")
            continue

        # Secret: .saved -- list everything saved about this user
        if lowered == ".saved":
            notes = saved_info.list_notes(current_user)
            if not notes:
                print(f"{DIM}Nothing saved yet. Use {RESET}{GREEN}{BOLD}.remember <text>{RESET}{DIM} to add something.{RESET}")
            else:
                print(f"{GRAY}Saved info for {BOLD}{current_user}{RESET}{GRAY}:{RESET}")
                for i, note in enumerate(notes, 1):
                    print(f"  {CYAN}{BOLD}{i}.{RESET} {note['text']} {DIM}[{note['added']}]{RESET}")
            continue

        # Secret: .forget-all -- wipe all saved info about this user
        if lowered == ".forget-all":
            success, msg = saved_info.forget_all(current_user)
            if success:
                print(f"{YELLOW}{BOLD}↻{RESET} {msg}")
            else:
                print(f"{RED}{BOLD}✗{RESET} {msg}")
            continue

        if lowered.startswith(".forget "):
            index_str = user_input[8:].strip()
            if not index_str.isdigit():
                print(f"{RED}{BOLD}✗{RESET} Usage: .forget <n> (use .saved to see note numbers)")
            else:
                success, msg = saved_info.forget(current_user, int(index_str))
                if success:
                    print(f"{GREEN}{BOLD}✓{RESET} {msg}")
                else:
                    print(f"{RED}{BOLD}✗{RESET} {msg}")
            continue

        # Secret: .siaird -- show saved info JSON and enable it for all future prompts
        if lowered == ".siaird":
            import json
            saved_data = saved_info.load_info(current_user)
            print(f"{GRAY}Saved info for {BOLD}{current_user}{RESET}{GRAY} (JSON):{RESET}")
            print(f"{CYAN}{json.dumps(saved_data, indent=2, ensure_ascii=False)}{RESET}")
            print(f"{YELLOW}{BOLD}→{RESET} This will now be included in all AI prompts.")
            # The saved_info is already auto-included via _with_saved_info() on line ~882
            continue

        context = engine.context_for(user_input)
        context = _with_saved_info(context, current_user)
        
        # Add chat history to context
        history = format_history_for_ai(chat_messages)
        if history:
            context['chat_history'] = history

        if len(user_input.split()) >= MIN_LEARN_WORDS:
            engine.learn(user_input)

        # Track user message
        chat_messages.append({
            "role": "user",
            "text": user_input,
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
        })

        answer, err, debug_info, write_blocks, plain_blocks, action_log, rounds = _run_ai_action_loop(
            engine, user_input, context, model=current_model
        )

        if err:
            print(f"{DIM}{GRAY}⚠ {err} (falling back to local engine){RESET}")

        if answer is None:
            error_msg = f"I don't know enough yet. Try /learn <sentence>"
            if current_mode == "prompt":
                from prompt_mode import show_prompt_error
                show_prompt_error(title="Flask Code", error_text=error_msg)
            else:
                print(f"{AI_NAME} {RED}{BOLD}∿{RESET} {BOLD}{error_msg}{RESET}")
        else:
            # Track AI response
            chat_messages.append({
                "role": "flask",
                "text": answer,
                "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
            })

            for line in action_log:
                print(f"  {line}")

            if current_mode == "prompt":
                from prompt_mode import show_prompt_response
                show_prompt_response(title="Flask Code", response_text=f"Flask: {strip_action_directives(answer)}")
            else:
                formatted_answer = format_response(strip_action_directives(answer))
                print(f"{AI_NAME} {CYAN}›{RESET} {formatted_answer}")

            # '-write'-tagged blocks: the AI already decided these should be
            # real files, so save them without asking.
            written = _save_write_blocks(write_blocks)
            if written:
                print(f"{GREEN}{BOLD}✓{RESET} Saved {len(written)} file(s): {', '.join(written)}")

            # Everything else with no directive: ask before saving.
            if plain_blocks and current_mode != "prompt":
                saved = _offer_to_save_plain_blocks(plain_blocks)
                if saved:
                    print(f"{GREEN}{BOLD}✓{RESET} Saved {len(saved)} file(s): {', '.join(saved)}")

        if debug_mode:
            print(_format_debug_line(debug_info))
            print(_format_directive_debug(rounds))
        
        # Auto-save chat after each message
        if chat_messages:
            success, save_msg, pin = chat_history.save_chat(current_user, chat_messages)
            if not success:
                print(f"{YELLOW}{BOLD}⚠{RESET} {BOLD}Failed to auto-save: {save_msg}{RESET}")


def main():
    try:
        _run_session()
    except RestartRequested:
        sys.exit(RESTART_EXIT_CODE)


if __name__ == "__main__":
    main()
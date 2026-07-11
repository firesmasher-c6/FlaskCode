"""
user-interface.py (Flask Code Desktop UI with Animations & Markdown)
Modern desktop chat UI based on Tkinter with smooth animations, markdown support, and a conversational layout.

Run: python user-interface.py
"""
import os
import re
import sys
import time
import threading
import html

import tkinter as tk
from tkinter import ttk, messagebox, simpledialog, font, scrolledtext

from engine import KnowledgeEngine
import gemini_client
import groq_client
import openrouter_client
import apikey_settings
import auth
import chat_history
import saved_info
from chat_loader import load_chat_history, save_chat_history, format_history_for_ai
from code_extractor import classify_blocks, strip_action_directives, save_code_block, resolve_extension
from file_handler import write_file
import shell_actions

# ============================================================================
# ANIMATIONS - Extracted from main.py
# ============================================================================
ANIMATION_PHASES = {
    "thinking":   ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"],
    "loading":    ["⠁", "⠂", "⠄", "⡀", "⢀", "⠠", "⠐", "⠈"],
    "processing": ["▖", "▘", "▝", "▗"],
    "spinner":    ["◐", "◓", "◑", "◒"],
    "dots":       ["⠋", "⠙", "⠚", "⠞", "⠖", "⠦", "⠴", "⠲", "⠳", "⠓"],
}

class AnimationFrame:
    """Manager for cycling through animation frames."""
    def __init__(self, phase_type="thinking"):
        self.frames = ANIMATION_PHASES.get(phase_type, ANIMATION_PHASES["thinking"])
        self.current = 0
    
    def next(self):
        frame = self.frames[self.current % len(self.frames)]
        self.current += 1
        return frame

# ============================================================================
# MARKDOWN SUPPORT
# ============================================================================
class MarkdownFormatter:
    """Simple markdown formatter for chat messages."""
    
    @staticmethod
    def format_text(text):
        """Convert markdown to formatted text."""
        # Code blocks (```...```)
        text = re.sub(
            r'```([^\n]*)\n(.*?)\n```',
            lambda m: f"\n[CODE: {m.group(1) or 'code'}]\n{m.group(2)}\n[/CODE]\n",
            text,
            flags=re.DOTALL
        )
        
        # Inline code (`...`)
        text = re.sub(r'`([^`]+)`', r'[CODE_INLINE]\1[/CODE_INLINE]', text)
        
        # Bold (**...**)
        text = re.sub(r'\*\*([^*]+)\*\*', r'[BOLD]\1[/BOLD]', text)
        
        # Italic (*...*)
        text = re.sub(r'\*([^*]+)\*', r'[ITALIC]\1[/ITALIC]', text)
        
        # Links ([text](url))
        text = re.sub(r'\[([^\]]+)\]\(([^)]+)\)', r'[\1 -> \2]', text)
        
        # Headers (# ...)
        text = re.sub(r'^### (.*?)$', r'[HEADER3]\1[/HEADER3]', text, flags=re.MULTILINE)
        text = re.sub(r'^## (.*?)$', r'[HEADER2]\1[/HEADER2]', text, flags=re.MULTILINE)
        text = re.sub(r'^# (.*?)$', r'[HEADER1]\1[/HEADER1]', text, flags=re.MULTILINE)
        
        # Lists (- ... or * ...)
        text = re.sub(r'^\s*[-*]\s+(.+)$', r'  • \1', text, flags=re.MULTILINE)
        
        return text
    
    @staticmethod
    def apply_tags(display_widget, text, start_idx):
        """Apply tags to formatted text in display widget."""
        markers = {
            '[BOLD]': ('[/BOLD]', 'bold'),
            '[ITALIC]': ('[/ITALIC]', 'italic'),
            '[CODE:': ('[/CODE]', 'code'),
            '[CODE_INLINE]': ('[/CODE_INLINE]', 'code'),
            '[HEADER1]': ('[/HEADER1]', 'header1'),
            '[HEADER2]': ('[/HEADER2]', 'header2'),
            '[HEADER3]': ('[/HEADER3]', 'header3'),
        }

        plain = []
        tags = []
        i = 0

        while i < len(text):
            matched = False
            for open_marker, (close_marker, tag_name) in markers.items():
                if text.startswith(open_marker, i):
                    if open_marker == '[CODE:':
                        end_marker = text.find(close_marker, i)
                        if end_marker == -1:
                            break
                        content_start = text.find('\n', i)
                        if content_start == -1 or content_start > end_marker:
                            break
                        content = text[content_start + 1:end_marker]
                        start_pos = len(''.join(plain))
                        plain.append(content)
                        end_pos = start_pos + len(content)
                        tags.append((tag_name, start_pos, end_pos))
                        i = end_marker + len(close_marker)
                    else:
                        end_marker = text.find(close_marker, i)
                        if end_marker == -1:
                            break
                        content = text[i + len(open_marker):end_marker]
                        start_pos = len(''.join(plain))
                        plain.append(content)
                        end_pos = start_pos + len(content)
                        tags.append((tag_name, start_pos, end_pos))
                        i = end_marker + len(close_marker)
                    matched = True
                    break
            if not matched:
                plain.append(text[i])
                i += 1

        plain_text = ''.join(plain)
        display_widget.insert(start_idx, plain_text)

        for tag_name, start_pos, end_pos in tags:
            tag_start = display_widget.index(f"{start_idx} + {start_pos} chars")
            tag_end = display_widget.index(f"{start_idx} + {end_pos} chars")
            display_widget.tag_add(tag_name, tag_start, tag_end)

# ============================================================================
# THEME LOADING FROM style.css
# ============================================================================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ASSETS_DIR = os.path.join(BASE_DIR, "assets")
STYLE_CSS_PATH = os.path.join(ASSETS_DIR, "style.css")

DEFAULT_THEME = {
    "app-title": "Flask Code",
    "window-width": "1200",
    "window-height": "780",
    "bg-color": "#0b1220",
    "panel-color": "#111827",
    "field-color": "#1f2937",
    "fg-color": "#e5e7eb",
    "dim-color": "#9ca3af",
    "border-color": "#334155",
    "accent-cyan": "#38bdf8",
    "accent-magenta": "#c084fc",
    "accent-green": "#22c55e",
    "accent-yellow": "#facc15",
    "accent-red": "#fb7185",
    "accent-blue": "#60a5fa",
    "accent-orange": "#f97316",
    "font-family": "Consolas",
    "font-size": "11",
    "title-font-size": "16",
}

_CSS_ROOT_RE = re.compile(r':root\s*\{([^}]*)\}', re.DOTALL)
_CSS_VAR_RE = re.compile(r'--([\w-]+)\s*:\s*([^;]+);')

def _strip_css_comments(text):
    return re.sub(r'/\*.*?\*/', '', text, flags=re.DOTALL)

def _load_theme(path=STYLE_CSS_PATH):
    """Load CSS custom properties from style.css."""
    theme = dict(DEFAULT_THEME)
    if not os.path.exists(path):
        return theme
    try:
        with open(path, "r", encoding="utf-8") as f:
            css = _strip_css_comments(f.read())
    except Exception:
        return theme
    
    root_match = _CSS_ROOT_RE.search(css)
    if not root_match:
        return theme
    
    for name, value in _CSS_VAR_RE.findall(root_match.group(1)):
        value = value.strip().strip('"').strip("'")
        if value:
            theme[name.lower()] = value
    return theme

THEME = _load_theme()

def _theme_int(key, fallback):
    try:
        return int(float(THEME.get(key, fallback)))
    except (TypeError, ValueError):
        return int(fallback)

# Extract theme values
BG_COLOR = THEME["bg-color"]
PANEL_COLOR = THEME["panel-color"]
FIELD_COLOR = THEME["field-color"]
FG_COLOR = THEME["fg-color"]
DIM_COLOR = THEME["dim-color"]
BORDER_COLOR = THEME.get("border-color", "#e5e5ea")
ACCENT_CYAN = THEME["accent-cyan"]
ACCENT_MAGENTA = THEME["accent-magenta"]
ACCENT_GREEN = THEME["accent-green"]
ACCENT_YELLOW = THEME["accent-yellow"]
ACCENT_RED = THEME["accent-red"]
ACCENT_BLUE = THEME["accent-blue"]
ACCENT_ORANGE = THEME["accent-orange"]

FONT_FAMILY = THEME["font-family"]
FONT_SIZE = _theme_int("font-size", 11)
TITLE_FONT_SIZE = _theme_int("title-font-size", 16)
WINDOW_WIDTH = _theme_int("window-width", 1200)
WINDOW_HEIGHT = _theme_int("window-height", 800)
APP_TITLE = THEME.get("app-title", "Flask Code")

# ============================================================================
# APP CONSTANTS
# ============================================================================
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

MIN_LEARN_WORDS = 4
MAX_ACTION_ROUNDS = 3
LAST_USER_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".flask")
LAST_USER_FILE = os.path.join(LAST_USER_DIR, "last_user.last")

BANNER_TEXT = """Flask Code
AI-Powered Code & Knowledge Assistant

Commands:
  /learn <sentence>       teach it something
  /stats                  show knowledge size
  /model <name>           switch AI model
  /apikey <1|2|3>         lock a .apikeys slot
  /help                   show this menu
  /logout                 logout
"""

# ============================================================================
# HELPERS
# ============================================================================
def _save_last_user(username):
    if not username:
        return
    try:
        os.makedirs(LAST_USER_DIR, exist_ok=True)
        with open(LAST_USER_FILE, "w", encoding="utf-8") as f:
            f.write(username)
    except Exception:
        pass

def _load_last_user():
    if not os.path.exists(LAST_USER_FILE):
        return None
    try:
        with open(LAST_USER_FILE, "r", encoding="utf-8") as f:
            name = f.read().strip()
        return name or None
    except Exception:
        return None

def _provider_for_model(model_name):
    return MODELS.get(model_name, MODELS[DEFAULT_MODEL])[0]

def _model_id_for(model_name):
    return MODELS.get(model_name, MODELS[DEFAULT_MODEL])[1]

def _client_for_model(model_name):
    return CLIENTS[_provider_for_model(model_name)]

# ============================================================================
# MAIN APP
# ============================================================================
class ChatGPTGUI:
    """Flask Code desktop GUI with animations and markdown support."""
    
    def __init__(self):
        self.root = tk.Tk()
        self.root.title(APP_TITLE)
        self.root.geometry(f"{WINDOW_WIDTH}x{WINDOW_HEIGHT}")
        self.root.configure(bg=BG_COLOR)
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
        
        # Load icon if available
        icon_path = os.path.join(ASSETS_DIR, "images", "ui_icon.png")
        if os.path.exists(icon_path):
            try:
                icon_photo = tk.PhotoImage(file=icon_path)
                self.root.iconphoto(False, icon_photo)
            except Exception:
                pass
        
        # Fonts
        self.mono_font = font.Font(family=FONT_FAMILY, size=FONT_SIZE)
        self.mono_bold = font.Font(family=FONT_FAMILY, size=FONT_SIZE, weight="bold")
        self.title_font = font.Font(family=FONT_FAMILY, size=TITLE_FONT_SIZE, weight="bold")
        self.small_font = font.Font(family=FONT_FAMILY, size=FONT_SIZE - 1)
        self.code_font = font.Font(family="Courier New", size=FONT_SIZE - 2)
        
        self.engine = None
        self.current_user = None
        self.current_model = DEFAULT_MODEL
        self.chat_messages = []
        self.is_waiting = False
        self.animation_frame = AnimationFrame("thinking")
        
        # Initialize
        last_user = _load_last_user()
        if last_user:
            self.current_user = last_user
            self._init_engine()
            self._show_chat_screen()
        else:
            self._show_login_screen()
    
    def _init_engine(self):
        """Initialize the knowledge engine."""
        try:
            self.engine = KnowledgeEngine()
            # Load chat history if exists
            if self.current_user:
                self.chat_messages = load_chat_history(self.current_user) or []
        except Exception as e:
            print(f"Failed to initialize engine: {e}")
    
    # -- LOGIN SCREEN
    def _show_login_screen(self):
        """Display login/register screen with smooth design."""
        self.login_frame = tk.Frame(self.root, bg=BG_COLOR)
        self.login_frame.pack(fill=tk.BOTH, expand=True)
        
        # Center container
        center = tk.Frame(self.login_frame, bg=BG_COLOR)
        center.pack(expand=True, padx=40)
        
        # Title
        title_label = tk.Label(
            center, text=APP_TITLE, font=self.title_font,
            bg=BG_COLOR, fg=FG_COLOR
        )
        title_label.pack(pady=(0, 8))
        
        subtitle = tk.Label(
            center, text="AI-Powered Code & Knowledge Assistant",
            font=self.small_font, bg=BG_COLOR, fg=DIM_COLOR
        )
        subtitle.pack(pady=(0, 40))
        
        # Login Card
        card = tk.Frame(center, bg=PANEL_COLOR, relief=tk.FLAT, bd=1, highlightthickness=1, highlightbackground=BORDER_COLOR)
        card.pack(fill=tk.X)
        
        # Fields
        fields_frame = tk.Frame(card, bg=PANEL_COLOR)
        fields_frame.pack(padx=24, pady=24, fill=tk.X)
        
        tk.Label(fields_frame, text="Username", font=self.mono_bold, bg=PANEL_COLOR, fg=FG_COLOR).pack(anchor=tk.W, pady=(0, 6))
        username_entry = tk.Entry(fields_frame, font=self.mono_font, bg=FIELD_COLOR, fg=FG_COLOR, insertbackground=ACCENT_CYAN, relief=tk.FLAT, bd=1)
        username_entry.pack(fill=tk.X, pady=(0, 16))
        
        tk.Label(fields_frame, text="Password", font=self.mono_bold, bg=PANEL_COLOR, fg=FG_COLOR).pack(anchor=tk.W, pady=(0, 6))
        password_entry = tk.Entry(fields_frame, font=self.mono_font, bg=FIELD_COLOR, fg=FG_COLOR, insertbackground=ACCENT_CYAN, relief=tk.FLAT, bd=1, show="•")
        password_entry.pack(fill=tk.X)
        
        error_label = tk.Label(card, text="", font=self.small_font, bg=PANEL_COLOR, fg=ACCENT_RED)
        error_label.pack(pady=(0, 16))
        
        def on_login():
            error_label.config(text="")
            username = username_entry.get().strip()
            password = password_entry.get()
            
            if not username or not password:
                error_label.config(text="Username and password required", fg=ACCENT_RED)
                return
            
            ok, msg, pin = auth.login(username, password)
            if ok:
                self.current_user = username
                self.chat_messages = load_chat_history(username) or []
                _save_last_user(username)
                self._init_engine()
                self.login_frame.destroy()
                self._show_chat_screen()
            else:
                error_label.config(text=msg, fg=ACCENT_RED)
        
        def on_register():
            error_label.config(text="")
            username = username_entry.get().strip()
            password = password_entry.get()
            
            if not username or not password:
                error_label.config(text="Username and password required")
                return
            
            ok, msg = auth.register(username, password)
            if ok:
                error_label.config(text="✓ Registered! Logging in…", fg=ACCENT_GREEN)
                self.root.after(800, on_login)
            else:
                error_label.config(text=msg, fg=ACCENT_RED)
        
        # Buttons
        button_row = tk.Frame(card, bg=PANEL_COLOR)
        button_row.pack(padx=24, pady=(0, 24), fill=tk.X)
        
        tk.Button(
            button_row, text="Login", font=self.mono_bold,
            bg=ACCENT_CYAN, fg="white", relief=tk.FLAT, padx=20, pady=10,
            command=on_login, activebackground=ACCENT_MAGENTA, activeforeground="white",
        ).pack(side=tk.LEFT, padx=(0, 10))
        
        tk.Button(
            button_row, text="Register", font=self.mono_font,
            bg=FIELD_COLOR, fg=ACCENT_CYAN, relief=tk.FLAT, padx=20, pady=10,
            command=on_register, activebackground=PANEL_COLOR, activeforeground=ACCENT_MAGENTA,
        ).pack(side=tk.LEFT)
        
        username_entry.bind("<Return>", lambda e: on_login())
        password_entry.bind("<Return>", lambda e: on_login())
        username_entry.focus_set()
    
    # -- CHAT SCREEN
    def _show_chat_screen(self):
        """Display main chat interface with ChatGPT-style layout."""
        self.chat_frame = tk.Frame(self.root, bg=BG_COLOR)
        self.chat_frame.pack(fill=tk.BOTH, expand=True)
        
        # ─── TOP BAR ───
        top_bar = tk.Frame(self.chat_frame, bg=PANEL_COLOR, height=56)
        top_bar.pack(fill=tk.X)
        top_bar.pack_propagate(False)
        
        # Add subtle border
        border = tk.Frame(top_bar, bg=BORDER_COLOR, height=1)
        border.pack(fill=tk.X, side=tk.BOTTOM)
        
        # Left section: Title
        left_section = tk.Frame(top_bar, bg=PANEL_COLOR)
        left_section.pack(side=tk.LEFT, padx=20, pady=12, fill=tk.Y)
        
        tk.Label(
            left_section, text=APP_TITLE, font=self.title_font,
            bg=PANEL_COLOR, fg=FG_COLOR
        ).pack(side=tk.LEFT)
        
        tk.Label(
            left_section, text=f" · {self.current_user}", font=self.mono_font,
            bg=PANEL_COLOR, fg=DIM_COLOR
        ).pack(side=tk.LEFT, padx=(8, 0))
        
        # Right section: Controls
        right_section = tk.Frame(top_bar, bg=PANEL_COLOR)
        right_section.pack(side=tk.RIGHT, padx=20, pady=12, fill=tk.Y)
        
        # Model selector
        model_frame = tk.Frame(right_section, bg=PANEL_COLOR)
        model_frame.pack(side=tk.LEFT, padx=(0, 16))
        
        tk.Label(
            model_frame, text="Model:", font=self.mono_font,
            bg=PANEL_COLOR, fg=DIM_COLOR
        ).pack(side=tk.LEFT, padx=(0, 8))
        
        self.model_var = tk.StringVar(value=self.current_model)
        model_combo = ttk.Combobox(
            model_frame, textvariable=self.model_var, values=list(MODELS.keys()),
            width=16, state="readonly", font=self.mono_font
        )
        model_combo.pack(side=tk.LEFT)
        model_combo.bind("<<ComboboxSelected>>", self._on_model_change)
        
        # Buttons
        tk.Button(
            right_section, text="Help", font=self.mono_font,
            bg=PANEL_COLOR, fg=ACCENT_CYAN, relief=tk.FLAT,
            padx=12, pady=6, command=self._show_help
        ).pack(side=tk.LEFT, padx=(0, 8))
        
        tk.Button(
            right_section, text="Logout", font=self.mono_font,
            bg=ACCENT_RED, fg="white", relief=tk.FLAT,
            padx=12, pady=6, command=self._logout
        ).pack(side=tk.LEFT)
        
        # ─── CHAT DISPLAY ───
        self.display = scrolledtext.ScrolledText(
            self.chat_frame, wrap=tk.WORD, bg=BG_COLOR, fg=FG_COLOR,
            font=self.code_font, insertbackground=ACCENT_CYAN, relief=tk.FLAT,
            borderwidth=0, padx=16, pady=16
        )
        self.display.pack(fill=tk.BOTH, expand=True, padx=0, pady=0)
        self.display.config(state=tk.DISABLED)
        self._setup_tags()
        
        # Welcome message
        self._log_system(f"✨ Welcome back, {self.current_user}!")
        if self.chat_messages:
            self._log_system(f"↻ Loaded {len(self.chat_messages)} previous message(s)")
        self._log_system("Type your message and press Enter. Use /help for commands.")
        self._log_system("")
        
        # ─── INPUT AREA ───
        input_frame = tk.Frame(self.chat_frame, bg=BG_COLOR)
        input_frame.pack(fill=tk.X, padx=20, pady=(8, 20))
        
        # Input with border
        input_wrapper = tk.Frame(input_frame, bg=FIELD_COLOR, relief=tk.FLAT, bd=1, highlightthickness=1, highlightbackground=BORDER_COLOR)
        input_wrapper.pack(fill=tk.X)
        
        input_inner = tk.Frame(input_wrapper, bg=FIELD_COLOR)
        input_inner.pack(fill=tk.X, padx=12, pady=8)
        
        tk.Label(
            input_inner, text=f"{self.current_user}›", font=self.mono_bold,
            bg=FIELD_COLOR, fg=ACCENT_GREEN
        ).pack(side=tk.LEFT, padx=(0, 10))
        
        self.input_entry = tk.Entry(
            input_inner, font=self.code_font, bg=FIELD_COLOR, fg=FG_COLOR,
            insertbackground=ACCENT_CYAN, relief=tk.FLAT, bd=0
        )
        self.input_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.input_entry.bind("<Return>", self._on_send)
        self.input_entry.bind("<Shift-Return>", self._on_newline)
        self.input_entry.focus_set()
        
        tk.Button(
            input_inner, text="Send", font=self.mono_bold, bg=ACCENT_CYAN,
            fg="white", relief=tk.FLAT, padx=16, pady=0, command=self._on_send,
            activebackground=ACCENT_MAGENTA, activeforeground="white"
        ).pack(side=tk.LEFT, padx=(10, 0))
    
    def _setup_tags(self):
        """Configure text tags for different message types."""
        d = self.display
        d.tag_config("user", foreground=ACCENT_GREEN, font=self.code_font)
        d.tag_config("assistant", foreground=ACCENT_CYAN, font=self.code_font)
        d.tag_config("system", foreground=DIM_COLOR, font=self.small_font)
        d.tag_config("error", foreground=ACCENT_RED, font=self.code_font)
        d.tag_config("dim", foreground=DIM_COLOR, font=self.small_font)
        d.tag_config("code", foreground=ACCENT_ORANGE, font=self.code_font, background=PANEL_COLOR)
        d.tag_config("bold", font=self.code_font, foreground=ACCENT_CYAN)
        d.tag_config("prompt", foreground=ACCENT_GREEN, font=self.code_font)
        d.tag_config("italic", font=self.code_font, foreground=ACCENT_MAGENTA)
        d.tag_config("header1", font=self.title_font, foreground=ACCENT_CYAN)
        d.tag_config("header2", font=self.mono_bold, foreground=ACCENT_BLUE)
        d.tag_config("header3", font=self.mono_bold, foreground=ACCENT_MAGENTA)
    
    def _log_raw(self, text, tag):
        """Insert text with tag into display."""
        def do():
            self.display.config(state=tk.NORMAL)
            self.display.insert(tk.END, text + "\n", tag)
            self.display.see(tk.END)
            self.display.config(state=tk.DISABLED)
        self.root.after(0, do)
    
    def _log_system(self, text):
        """Log system message with animation."""
        self._log_raw(text, "system")
    
    def _log_error(self, text):
        """Log error message."""
        self._log_raw("✗ " + text, "error")
    
    def _append_user_message(self, text):
        """Add user message to display with animation."""
        def do():
            self.display.config(state=tk.NORMAL)
            self.display.insert(tk.END, f"{self.current_user} > ", "prompt")
            self.display.insert(tk.END, text + "\n")
            self.display.see(tk.END)
            self.display.config(state=tk.DISABLED)
        self.root.after(0, do)
    
    def _append_ai_message(self, text):
        """Add AI message with typing animation."""
        def animate_typing():
            self.display.config(state=tk.NORMAL)
            self.display.insert(tk.END, "assistant > ", "assistant")
            
            formatted_text = MarkdownFormatter.format_text(text)
            MarkdownFormatter.apply_tags(self.display, formatted_text, self.display.index(tk.INSERT))
            
            self.display.insert(tk.END, "\n")
            self.display.see(tk.END)
            self.display.config(state=tk.DISABLED)
            self.is_waiting = False
        
        thread = threading.Thread(target=animate_typing, daemon=True)
        thread.start()
    
    def _animate_loading(self):
        """Show loading spinner."""
        frames = ANIMATION_PHASES["thinking"]
        for _ in range(20):  # Animate for a bit
            if not self.is_waiting:
                break
            # Could update display here if needed
            time.sleep(0.1)
    
    def _show_help(self):
        """Display help text."""
        self._log_system(BANNER_TEXT)
    
    def _on_model_change(self, event=None):
        """Handle model selection change."""
        self.current_model = self.model_var.get()
        self._log_system(f"→ Switched to {self.current_model}")
    
    def _logout(self):
        """Logout and return to login screen."""
        if self.chat_messages and self.current_user:
            save_chat_history(self.current_user, self.chat_messages)
            chat_history.save_chat(self.current_user, self.chat_messages)
        _save_last_user(self.current_user)
        self.current_user = None
        self.chat_messages = []
        self.chat_frame.destroy()
        self._show_login_screen()
    
    def _on_close(self):
        """Save and exit."""
        if self.chat_messages and self.current_user:
            save_chat_history(self.current_user, self.chat_messages)
            chat_history.save_chat(self.current_user, self.chat_messages)
        self.root.destroy()
    
    def _on_newline(self, event=None):
        """Handle Shift+Return for newline."""
        self.input_entry.insert(tk.INSERT, "\n")
        return "break"
    
    def _on_send(self, event=None):
        """Handle message send."""
        msg = self.input_entry.get().strip()
        self.input_entry.delete(0, tk.END)
        
        if not msg:
            return
        
        self._append_user_message(msg)
        self._run_ai_turn(msg)
    
    def _run_ai_turn(self, user_msg):
        """Run AI in background thread."""
        def do_ai():
            self.is_waiting = True
            self._log_system("assistant is thinking…")
            
            try:
                context = self.engine.context_for(user_msg)
                history = format_history_for_ai(self.chat_messages)
                if history:
                    context["chat_history"] = history
                
                if len(user_msg.split()) >= MIN_LEARN_WORDS:
                    self.engine.learn(user_msg)
                
                self.chat_messages.append({
                    "role": "user", "text": user_msg,
                    "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
                })
                
                # Get AI answer
                client = _client_for_model(self.current_model)
                model_id = _model_id_for(self.current_model)
                answer, err, debug_info = None, None, None
                
                if client.has_api_key(self.current_user):
                    answer, err, debug_info = client.ask(user_msg, context, model=model_id)
                
                if answer is None:
                    answer = self.engine.generate(seed=context.get("seed"))
                
                self.chat_messages.append({
                    "role": "assistant", "text": answer,
                    "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
                })
                
                self._append_ai_message(answer)
                
                if self.current_user:
                    save_chat_history(self.current_user, self.chat_messages)
            
            except Exception as e:
                self._log_error(str(e))
            
            finally:
                self.is_waiting = False
        
        thread = threading.Thread(target=do_ai, daemon=True)
        thread.start()
    
    def run(self):
        """Start the GUI."""
        self.root.mainloop()


if __name__ == "__main__":
    app = ChatGPTGUI()
    app.run()
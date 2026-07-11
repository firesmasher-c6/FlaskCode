import tkinter as tk
from tkinter import scrolledtext, font
import threading
import queue
import time

# Color scheme matching Flask's aesthetic
BG_COLOR = "#0a0e27"
FG_COLOR = "#e0e6ff"
ACCENT_CYAN = "#00d4ff"
ACCENT_MAGENTA = "#ff00ff"
ACCENT_GREEN = "#00ff00"
ACCENT_YELLOW = "#ffff00"
ACCENT_RED = "#ff0000"
ACCENT_BLUE = "#0099ff"
ACCENT_ORANGE = "#ff8800"

class AnimationFrames:
    """Animation frames for different states."""
    # Braille spinners - smooth and elegant
    THINKING = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
    
    # Rotating corners for reading
    READING = ["⌜", "⌝", "⌞", "⌟"]
    
    # Pulsing wave for solving
    SOLVING = ["▮▯▯", "▯▮▯", "▯▯▮"]
    
    # Smooth gradient bar for generating
    GENERATING = ["▁", "▂", "▃", "▄", "▅", "▆", "▇", "█", "▇", "▆", "▅", "▄", "▃", "▂"]
    
    # Smooth curve for answering
    ANSWERING = ["◜", "◠", "◝", "◞"]
    
    # Sending animation - bouncing dots
    SENDING = ["●○○", "○●○", "○○●"]
    
    # Wave pulse animation
    WAVE = ["▐ ▌", "▕ ▎", "▔ ▔", "▖ ▗"]
    
    # Circular spinner (smooth rotation)
    SPINNER = ["◡", "⊙", "◠"]
    
    # Double pulse
    DOUBLE_PULSE = ["◐", "◑", "◒", "◓"]

class StatusIndicator:
    """Manages AI processing status and animations."""
    def __init__(self):
        self.state = None
        self.start_time = None
        self.frame_index = 0
        self.warnings = []
    
    def start(self, state):
        self.state = state
        self.start_time = time.time()
        self.frame_index = 0
        self.warnings = []
    
    def stop(self):
        self.state = None
        self.start_time = None
    
    def get_elapsed(self):
        if self.start_time is None:
            return 0
        return time.time() - self.start_time
    
    def get_frame(self):
        """Get the next animation frame based on current state."""
        frames = {
            "sending": AnimationFrames.SENDING,
            "thinking": AnimationFrames.THINKING,
            "reading": AnimationFrames.READING,
            "solving": AnimationFrames.SOLVING,
            "generating": AnimationFrames.GENERATING,
            "answering": AnimationFrames.ANSWERING,
            "wave": AnimationFrames.WAVE,
            "spinner": AnimationFrames.SPINNER,
            "pulse": AnimationFrames.DOUBLE_PULSE,
        }
        
        if self.state not in frames:
            return "⏳"
        
        frame_set = frames[self.state]
        frame = frame_set[self.frame_index % len(frame_set)]
        self.frame_index += 1
        return frame
    
    def check_warnings(self):
        if self.start_time is None:
            return None
        
        elapsed = self.get_elapsed()
        
        if elapsed > 1200 and "20min" not in self.warnings:
            self.warnings.append("20min")
            return "TIMEOUT", "Ai took too long than 20 minutes, cancelled request"
        
        if elapsed > 120 and "2min" not in self.warnings:
            self.warnings.append("2min")
            return "NOTICE", "Ai taking more than 2 minutes...."
        
        if elapsed > 30 and "30s" not in self.warnings:
            self.warnings.append("30s")
            return "WARNING", "Ai taking more than usual...."
        
        return None

class CustomTerminal:
    def __init__(self, send_callback):
        """
        send_callback: function(message) called when user submits input
        """
        self.send_callback = send_callback
        self.window = None
        self.text_display = None
        self.input_field = None
        self.message_queue = queue.Queue()
        self.running = False
        self.status = StatusIndicator()
        self.animation_thread = None

    def create_window(self):
        """Create and configure the terminal window."""
        if self.window is not None:
            self.window.lift()
            return

        self.running = True
        self.window = tk.Tk()
        self.window.title("Flask Custom Terminal")
        self.window.geometry("900x680")
        self.window.configure(bg=BG_COLOR)
        self.window.protocol("WM_DELETE_WINDOW", self.close_window)

        # Create monospace font
        mono_font = font.Font(family="JetBrains Mono", size=10)
        bold_font = font.Font(family="JetBrains Mono", size=10, weight="bold")
        title_font = font.Font(family="JetBrains Mono", size=12, weight="bold")

        # Top banner
        banner_frame = tk.Frame(self.window, bg=ACCENT_CYAN, height=70)
        banner_frame.pack(fill=tk.X, side=tk.TOP)
        banner_frame.pack_propagate(False)

        banner_label = tk.Label(
            banner_frame,
            text="⚙ FLASK CODE — terminal thought engine",
            font=title_font,
            bg=ACCENT_CYAN,
            fg=BG_COLOR,
        )
        banner_label.pack(pady=12)

        # Status frame
        status_frame = tk.Frame(self.window, bg="#0f1335", height=30)
        status_frame.pack(fill=tk.X, side=tk.TOP)
        status_frame.pack_propagate(False)

        self.status_indicator = tk.Label(
            status_frame,
            text="ready",
            font=mono_font,
            bg="#0f1335",
            fg=ACCENT_GREEN,
        )
        self.status_indicator.pack(side=tk.LEFT, padx=10, pady=5)

        separator = tk.Label(
            status_frame,
            text="―" * 80,
            font=mono_font,
            bg="#0f1335",
            fg="#333366",
        )
        separator.pack(side=tk.LEFT, fill=tk.X, expand=True)

        # Text display area (scrolled text widget)
        self.text_display = scrolledtext.ScrolledText(
            self.window,
            wrap=tk.WORD,
            bg=BG_COLOR,
            fg=FG_COLOR,
            font=mono_font,
            insertbackground=ACCENT_CYAN,
            selectbackground=ACCENT_MAGENTA,
            selectforeground=BG_COLOR,
            height=20,
            width=90,
        )
        self.text_display.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        self.text_display.config(state=tk.DISABLED)

        # Configure tags for colors and styles
        self._setup_tags()

        # Input frame
        input_frame = tk.Frame(self.window, bg=BG_COLOR)
        input_frame.pack(fill=tk.X, padx=5, pady=5)

        prompt_label = tk.Label(
            input_frame,
            text="you›",
            font=bold_font,
            bg=BG_COLOR,
            fg=ACCENT_GREEN,
        )
        prompt_label.pack(side=tk.LEFT, padx=(0, 5))

        self.input_field = tk.Entry(
            input_frame,
            font=mono_font,
            bg="#1a1f3a",
            fg=FG_COLOR,
            insertbackground=ACCENT_CYAN,
            border=1,
            relief=tk.SOLID,
        )
        self.input_field.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.input_field.bind("<Return>", self._on_submit)
        self.input_field.focus()

        send_btn = tk.Button(
            input_frame,
            text="Send",
            font=bold_font,
            bg=ACCENT_CYAN,
            fg=BG_COLOR,
            activebackground=ACCENT_MAGENTA,
            activeforeground=BG_COLOR,
            border=0,
            padx=10,
            command=self._on_submit,
        )
        send_btn.pack(side=tk.LEFT, padx=(5, 0))

        # Bottom info bar
        info_frame = tk.Frame(self.window, bg="#0f1335", height=25)
        info_frame.pack(fill=tk.X, side=tk.BOTTOM)
        info_frame.pack_propagate(False)

        self.info_label = tk.Label(
            info_frame,
            text="Type your message and press Enter",
            font=mono_font,
            bg="#0f1335",
            fg=ACCENT_BLUE,
        )
        self.info_label.pack(side=tk.LEFT, padx=10, pady=3)

        # Start message queue processor
        self._process_queue()

    def _setup_tags(self):
        """Setup text tags for colored output and styles."""
        if self.text_display is None:
            return

        self.text_display.tag_config("cyan", foreground=ACCENT_CYAN)
        self.text_display.tag_config("magenta", foreground=ACCENT_MAGENTA)
        self.text_display.tag_config("green", foreground=ACCENT_GREEN)
        self.text_display.tag_config("yellow", foreground=ACCENT_YELLOW)
        self.text_display.tag_config("red", foreground=ACCENT_RED)
        self.text_display.tag_config("blue", foreground=ACCENT_BLUE)
        self.text_display.tag_config("orange", foreground=ACCENT_ORANGE)
        self.text_display.tag_config("dim", foreground="#666666")
        self.text_display.tag_config("bold", foreground=FG_COLOR, font=("Courier New", 11, "bold"))
        self.text_display.tag_config("banner", foreground=ACCENT_MAGENTA)
        self.text_display.tag_config("bold_cyan", foreground=ACCENT_CYAN, font=("Courier New", 11, "bold"))
        self.text_display.tag_config("bold_green", foreground=ACCENT_GREEN, font=("Courier New", 11, "bold"))
        self.text_display.tag_config("bold_red", foreground=ACCENT_RED, font=("Courier New", 11, "bold"))
        self.text_display.tag_config("bold_yellow", foreground=ACCENT_YELLOW, font=("Courier New", 11, "bold"))
        self.text_display.tag_config("notice", foreground=ACCENT_ORANGE, font=("Courier New", 10, "bold"))
        self.text_display.tag_config("timeout", foreground=ACCENT_RED, font=("Courier New", 11, "bold"))

    def _on_submit(self, event=None):
        """Handle user input submission."""
        message = self.input_field.get().strip()
        if message:
            # Display user message
            self.append_output(f"you› {message}\n", tag="bold_green")
            self.input_field.delete(0, tk.END)
            self.input_field.config(state=tk.DISABLED)  # Disable input during send/process
            
            # Start sending animation
            self.status.start("sending")
            self.set_info("Sending message...")
            
            # Call the send callback in a separate thread to avoid blocking
            threading.Thread(target=self._send_with_status, args=(message,), daemon=True).start()

    def _send_with_status(self, message):
        """Send message and handle status updates."""
        try:
            # Transition from sending to thinking after a brief moment
            time.sleep(0.3)
            self.status.start("thinking")
            self.set_info("AI is thinking...")
            
            # Call the actual send callback
            self.send_callback(message)
        finally:
            self.status.stop()
            self.input_field.config(state=tk.NORMAL)  # Re-enable input
            self.input_field.focus()
            self.message_queue.put((None, None, "status_update"))

    def append_output(self, text, color=None, tag=None):
        """Append text to the display (thread-safe via queue)."""
        self.message_queue.put((text, color, tag))

    def _process_queue(self):
        """Process queued messages from the message queue."""
        try:
            while True:
                item = self.message_queue.get_nowait()
                text, color, tag = item
                
                if tag == "status_update":
                    self._update_status_display()
                elif self.text_display is not None:
                    self.text_display.config(state=tk.NORMAL)
                    if tag:
                        self.text_display.insert(tk.END, text, tag)
                    elif color:
                        self.text_display.insert(tk.END, text, color)
                    else:
                        self.text_display.insert(tk.END, text)
                    self.text_display.see(tk.END)
                    self.text_display.config(state=tk.DISABLED)
        except queue.Empty:
            pass

        # Update animation if processing
        if self.status.state:
            self._update_animation()

        if self.running and self.window:
            self.window.after(100, self._process_queue)

    def _update_animation(self):
        """Update the status animation and check for warnings."""
        frame = self.status.get_frame()
        elapsed = self.status.get_elapsed()
        state = self.status.state
        
        # Map states to friendly display names
        state_labels = {
            "sending": "SENDING",
            "thinking": "THINKING",
            "reading": "READING",
            "solving": "SOLVING",
            "generating": "GENERATING",
            "answering": "ANSWERING",
            "wave": "PROCESSING",
            "spinner": "LOADING",
            "pulse": "SYNCING",
        }
        state_text = state_labels.get(state, state.upper())
        
        warning = self.status.check_warnings()
        
        if warning:
            warn_type, warn_msg = warning
            self._show_warning(warn_type, warn_msg)
            if warn_type == "TIMEOUT":
                self.status.stop()
                return
        
        # Format status with better spacing
        status_display = f"{frame} {state_text} ({elapsed:.1f}s)"
        self._update_status_display(status_display)

    def _update_status_display(self, status_text=None):
        """Update the status indicator label with state-specific colors."""
        if status_text is None:
            status_text = "ready"
            color = ACCENT_GREEN
        else:
            # Color based on current state for better visual feedback
            state = self.status.state
            if "TIMEOUT" in status_text or "error" in status_text.lower():
                color = ACCENT_RED
            elif "WARNING" in status_text or "NOTICE" in status_text:
                color = ACCENT_ORANGE
            elif state == "sending":
                color = ACCENT_MAGENTA
            elif state == "thinking":
                color = ACCENT_YELLOW
            elif state == "generating":
                color = ACCENT_GREEN
            elif state == "answering":
                color = ACCENT_CYAN
            else:
                color = ACCENT_BLUE
        
        if self.status_indicator:
            self.status_indicator.config(text=status_text, fg=color)

    def _show_warning(self, warn_type, message):
        """Display a warning message in the terminal."""
        warning_text = f"\n---< {warn_type} >---\n{message}\n\n"
        tag = "timeout" if warn_type == "TIMEOUT" else "notice"
        self.message_queue.put((warning_text, None, tag))

    def set_info(self, info_text):
        """Update the info label at the bottom."""
        if self.info_label and self.window:
            self.info_label.config(text=info_text)

    def close_window(self):
        """Close the terminal window."""
        self.running = False
        if self.window:
            self.window.destroy()
            self.window = None
            self.text_display = None
            self.input_field = None

    def is_open(self):
        """Check if the terminal window is open."""
        return self.window is not None and self.running

    def show_banner(self):
        """Display the Flask banner in the terminal."""
        banner = f"""
╔══════════════════════════════════════════════════════════════╗
║                                                              ║
║     F L A S K   C O D E                                      ║
║     >> terminal thought engine <<                            ║
║                                                              ║
╚══════════════════════════════════════════════════════════════╝

"""
        self.append_output(banner, tag="banner")
        self.append_output("Type your message and press Enter or click Send\n", tag="dim")
        self.append_output("Commands: clear, exit, help, file <name>\n\n", tag="dim")
import tkinter as tk
from tkinter import simpledialog, messagebox

class PromptDialog:
    """Single-message prompt dialog for Flask in prompt mode."""
    
    def __init__(self):
        self.root = tk.Tk()
        self.root.withdraw()  # Hide main window
        self.result = None
    
    def ask_message(self, title="Flask Code", prompt_text="You:", initial=""):
        """Show a prompt dialog and return user input."""
        self.result = simpledialog.askstring(
            title,
            prompt_text,
            parent=self.root,
            initialvalue=initial
        )
        return self.result
    
    def show_response(self, title="Flask Code", response_text=""):
        """Show Flask's response in a messagebox."""
        messagebox.showinfo(title, response_text, parent=self.root)
    
    def show_error(self, title="Flask Code", error_text=""):
        """Show an error message."""
        messagebox.showerror(title, error_text, parent=self.root)
    
    def cleanup(self):
        """Clean up the Tk window."""
        try:
            self.root.destroy()
        except:
            pass


def get_registration_input(title="Flask Code - Register"):
    """
    Show a small tkinter form with Username / Password / Confirm password
    fields and a Submit button. Returns (username, password) on submit,
    or None if the window is cancelled/closed or the passwords don't match.
    """
    root = tk.Tk()
    root.title(title)
    root.resizable(False, False)
    root.attributes("-topmost", True)

    result = {"value": None}

    frame = tk.Frame(root, padx=16, pady=16)
    frame.pack()

    tk.Label(frame, text="Username:").grid(row=0, column=0, sticky="e", pady=4)
    username_entry = tk.Entry(frame, width=26)
    username_entry.grid(row=0, column=1, pady=4)

    tk.Label(frame, text="Password:").grid(row=1, column=0, sticky="e", pady=4)
    password_entry = tk.Entry(frame, width=26, show="*")
    password_entry.grid(row=1, column=1, pady=4)

    tk.Label(frame, text="Confirm password:").grid(row=2, column=0, sticky="e", pady=4)
    confirm_entry = tk.Entry(frame, width=26, show="*")
    confirm_entry.grid(row=2, column=1, pady=4)

    error_label = tk.Label(frame, text="", fg="red")
    error_label.grid(row=3, column=0, columnspan=2, pady=(4, 0))

    def submit(event=None):
        username = username_entry.get().strip()
        password = password_entry.get()
        confirm = confirm_entry.get()

        if not username:
            error_label.config(text="Username is required")
            return
        if password != confirm:
            error_label.config(text="Passwords don't match")
            confirm_entry.delete(0, tk.END)
            return

        result["value"] = (username, password)
        root.destroy()

    def cancel(event=None):
        root.destroy()

    btn_frame = tk.Frame(frame)
    btn_frame.grid(row=4, column=0, columnspan=2, pady=(12, 0))
    tk.Button(btn_frame, text="Submit", width=10, command=submit).pack(side="left", padx=4)
    tk.Button(btn_frame, text="Cancel", width=10, command=cancel).pack(side="left", padx=4)

    root.bind("<Return>", submit)
    root.bind("<Escape>", cancel)
    root.protocol("WM_DELETE_WINDOW", cancel)

    root.update_idletasks()
    x = (root.winfo_screenwidth() - root.winfo_reqwidth()) // 2
    y = (root.winfo_screenheight() - root.winfo_reqheight()) // 2
    root.geometry(f"+{x}+{y}")

    username_entry.focus_set()
    root.mainloop()

    return result["value"]


def get_prompt_input(title="Flask Code", prompt_text="You:"):
    """
    Get single user input via dialog.
    Returns the user input string or None if cancelled.
    """
    dialog = PromptDialog()
    user_input = dialog.ask_message(title=title, prompt_text=prompt_text)
    dialog.cleanup()
    return user_input


def show_prompt_response(title="Flask Code", response_text=""):
    """
    Show Flask's response in a dialog.
    """
    dialog = PromptDialog()
    dialog.show_response(title=title, response_text=response_text)
    dialog.cleanup()


def show_prompt_error(title="Flask Code", error_text=""):
    """
    Show an error message in a dialog.
    """
    dialog = PromptDialog()
    dialog.show_error(title=title, error_text=error_text)
    dialog.cleanup()


def run_prompt_interaction(callback):
    """Run a single prompt interaction."""
    user_input = get_prompt_input(
        title="Flask Code",
        prompt_text="You:"
    )
    
    if user_input is not None and user_input.strip():
        # Process the input through callback
        response = callback(user_input.strip())
        if response:
            show_prompt_response(
                title="Flask Code",
                response_text=f"Flask: {response}"
            )
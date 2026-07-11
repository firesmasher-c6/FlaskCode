# Flask Code Guide

This guide explains setup, API key management, running the app, and the main usage patterns for Flask Code.

> This project is only tested on Windows. Flask Code is not an AI itself; it transforms an AI into an AI agent.


## 1. Setup

1. Install Python 3.10 or later.
2. Install dependencies:

```bash
python -m pip install -r requirements.txt
```

3. Copy the API key template into a live `.apikeys` file:

```bash
copy .apikeys_example .apikeys
```

4. Edit `.apikeys` and replace placeholder values with your actual API keys.

Add the launcher scripts `flaskc.ps1`, `flaskcode.ps1`, and `flck.ps1` to your PATH so you can invoke the app from PowerShell. Add `bin/launch.py` to PATH to launch the GUI conveniently.

## 2. API Key Format

The app expects `.apikeys` in YAML format with keys named `key_1`, `key_2`, and `key_3`.

Example:

```yaml
key_1: "AIabc123..."
key_2: "AIdef456..."
key_3: "AIghi789..."
```

### How keys are used

- `key_1`, `key_2`, `key_3` are provider slots.
- `key_3` is commonly used for OpenRouter fallback.
- The app may also use the `GEMINI_API_KEY` environment variable as an extra key source.
- Comment lines starting with `-!` are supported and ignored.

## 3. Launch Options

### Terminal mode

```bash
python main.py
```

### GUI mode

```bash
python user-interface.py
```

The GUI mode uses Tkinter, so make sure your Python install has Tk support enabled.

## 4. Basic Commands

Use the chat prompt and built-in commands to control the app.

- `/register-as` — open registration popup
- `/login-as <name> <password>` — log in
- `/apikey <1|2|3>` — switch API key slot
- `/model <name>` — change provider mode
- `/help` — show command help
- `/exit` — quit the application

## 5. Provider Tips

- `gemini` is the default provider.
- `openrouter` and `groq` require saved keys or configured slots.
- Use `/apikey 1`, `/apikey 2`, or `/apikey 3` to choose the slot that should be used.

## 6. Common Troubleshooting

### GUI does not open

- Ensure Tkinter is installed and available.
- On Windows, install Python with Tcl/Tk support.
- On Linux, install `python3-tk` or your distribution equivalent.

### `.apikeys` is missing or invalid

- Copy `.apikeys_example` to `.apikeys`.
- Replace placeholders with valid keys.
- Do not commit `.apikeys` to Git.

### Dependency issues

- Run:

```bash
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

## 7. Release Guidance

- Keep `.apikeys` private and ensure it remains excluded by `.gitignore`.
- Share `.apikeys_example` but never the real `.apikeys` file.
- Include this guide and `README.md` in your GitHub repo for new users.

## 8. Recommended GitHub Setup

- Add `README.md` and `Guide.md` to the repository root.
- Keep `.gitignore` updated with `.apikeys` and local Python artifacts.
- Use `requirements.txt` to document dependencies and runtime notes.

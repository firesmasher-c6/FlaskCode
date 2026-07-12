# FlaskCode-Server

Linux-only Flask REST API server. No GUI. Terminal/CLI admin console runs alongside the HTTP server in the same process.

---

## Setup

```bash
pip install -r requirements.txt
```

Create a `.apikeys` file next to `server.py` (YAML format):

```yaml
key_1: "AIza..."          # Gemini key
key_2: YOUR_API_KEY_HERE  # unused slot
key_3: YOUR_API_KEY_HERE  # unused slot
```

---

## Start the server

```bash
# Localhost only (default, safest)
python server.py

# Custom port
python server.py --port 8080

# All interfaces (LAN/remote clients)
python server.py --public --port 5000

# No admin console (pure daemon mode)
python server.py --no-console
```

The admin console appears in your terminal. Type `help` to see available commands.

---

## Admin console commands

| Command | What it does |
|---|---|
| `status` | Knowledge stats + debug mode |
| `debug on/off` | Toggle debug info in API responses |
| `learn <text>` | Teach the local engine |
| `reset` | Wipe and reseed knowledge base |
| `users` | List registered accounts + PINs |
| `chats` | List saved chats |
| `clear-outputs` | Wipe the `outputs/` folder |
| `models` | List available AI models |
| `exit` / `quit` | Stop the server |

---

## REST API reference

All POST bodies are JSON. All responses are JSON with an `ok` boolean.

### Auth

```
POST /auth/register          { username, password }
POST /auth/login             { username, password }
POST /auth/logout            { username }
POST /auth/change-password   { username, current_password, new_password }
POST /auth/login-pin         { pin }
```

### User info

```
GET  /me?username=<u>
GET  /stats?username=<u>&model=<m>
```

### Chat

```
POST /chat                   { username, message, model? }
GET  /chat/history?username=<u>
POST /chat/load              { username, pin }
POST /chat/clear             { username }
POST /chat/export            { username }
```

**Chat response shape:**

```json
{
  "ok": true,
  "answer": "...",
  "error": null,
  "action_log": ["✓ ran: ls -la", "    file1 file2"],
  "saved_files": ["output.py"],
  "plain_blocks": [{"language": "python", "code": "..."}],
  "debug": null
}
```

`plain_blocks` are code blocks the AI produced with no auto-save directive — the client should ask the user whether to save them, then POST to `/files/save-block`.

### Knowledge

```
POST /learn                  { username, sentence }
POST /reset-knowledge        {}
```

### Files

```
GET  /files
POST /files/read             { username, filename }
POST /files/read-path        { username, filepath }
POST /files/write            { username, filename, content }
POST /files/clear-outputs    {}
POST /files/save-block       { language, code, filename }
```

### Saved info (AI memory)

```
POST /remember               { username, text }
GET  /remember?username=<u>
POST /remember/forget        { username, index }
POST /remember/forget-all    { username }
```

### API keys

```
POST /apikey/set-slot        { username, slot }     # 1/2/3 — Gemini
POST /apikey/set-groq        { username, key }
POST /apikey/set-openrouter  { username, key }
```

### Misc

```
POST /ping                   { username?, model? }
GET  /clock?username=<u>&model=<m>
GET  /health
GET  /models
POST /debug/on
POST /debug/off
```

---

## Models

| Name | Provider |
|---|---|
| `3.1-flash-lite` *(default)* | Gemini |
| `3.1-flash` | Gemini |
| `3.5-flash` | Gemini |
| `llama-3.3-70b` | Groq |
| `gpt-oss-20b` | OpenRouter |

---

## File structure

```
server.py               ← entry point (run this)
engine.py               ← local Markov knowledge engine
auth.py                 ← user registration/login
chat_history.py         ← chat persistence + PINs
chat_loader.py          ← YAML chat load/save
saved_info.py           ← per-user AI memory notes
file_handler.py         ← file read/write (Linux paths)
shell_actions.py        ← bash command runner (Linux only)
code_extractor.py       ← code block parsing + save
markdown_highlighter.py ← ANSI syntax highlighting
apikey_settings.py      ← per-user API key settings
gemini_client.py        ← Gemini API client
groq_client.py          ← Groq API client
openrouter_client.py    ← OpenRouter API client
requirements.txt
.apikeys                ← your API keys (YAML, not committed)
knowledge.db            ← SQLite knowledge base (auto-created)
users.env               ← registered users (auto-created)
users.pins              ← user PINs (auto-created)
chats/                  ← saved chat YAML files
outputs/                ← AI-generated file outputs
saved-info/             ← per-user memory JSON files
.flask/user-settings/   ← per-user API key preferences
```

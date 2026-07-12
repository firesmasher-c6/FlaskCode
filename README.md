# FlaskCode Client  (`flaskcc`)

A feature-complete terminal client for **FlaskCode-Server**.  
Zero dependencies — pure Python 3.9+ stdlib only.

---

## Quick Start

```bash
# Linux / macOS
chmod +x flaskcc.sh
./flaskcc.sh localhost@5000
./flaskcc.sh 192.168.1.5@5000 -p mySecret

# Windows (PowerShell)
.\flaskcc.ps1 localhost@5000
.\flaskcc.ps1 192.168.1.5@5000 -Pass mySecret

# Or directly with Python (cross-platform)
python flaskcc.py localhost@5000 --pass mySecret
```

---

## Install in PATH (optional)

**Linux / macOS**
```bash
sudo cp flaskcc.sh /usr/local/bin/flaskcc
sudo chmod +x /usr/local/bin/flaskcc
# then:
flaskcc localhost@5000 -p mySecret
```

**Windows** — add the folder containing `flaskcc.ps1` to your `$PATH`,
then set the execution policy if needed:
```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
# then:
flaskcc localhost@5000 -Pass mySecret
```

---

## Command Line Flags

| Flag | Short | Description |
|------|-------|-------------|
| `--pass PASSWORD` | `-p` | Server password (from `.conf/server_config`) |
| `--user USERNAME` | `-u` | Auto-login on startup (prompts for password) |
| `--no-encrypt` | — | Send password in plain text |

---

## Interactive Commands

Once connected, everything runs from the REPL prompt:

```
alice@flask› [3.1-flash-lite] _
```

### Auth
| Command | What it does |
|---|---|
| `register <user> <pass>` | Create a new account |
| `login <user> <pass>` | Log in |
| `login-pin <pin>` | Log in with a saved PIN |
| `logout` | Save chat and log out |
| `passwd <old> <new>` | Change your password |
| `whoami` | Show username + PIN |

### Chat
| Command | What it does |
|---|---|
| *(any text)* | Send a message to FlaskCode AI |
| `model [name]` | Show or switch the active model |
| `models` | List all available models |
| `history` | Print your full chat history |
| `load <pin>` | Load a saved chat by PIN |
| `clear` | Clear your chat history |
| `export` | Export chat to a `.txt` file on the server |

### Knowledge
| Command | What it does |
|---|---|
| `learn <sentence>` | Teach the server's knowledge engine |
| `reset-knowledge` | Wipe + reseed the knowledge base |

### Files
| Command | What it does |
|---|---|
| `files` | List files available on the server |
| `read <filename>` | Read a file by name |
| `readpath <path>` | Read a file by absolute path |
| `write <filename> [content]` | Write/create a file |
| `save-block` | Interactively save a code block |
| `clear-outputs` | Wipe the server `outputs/` folder |

### Remember (notes)
| Command | What it does |
|---|---|
| `remember <text>` | Save a note to your profile |
| `notes` | List all your saved notes |
| `forget <index>` | Delete a note by index |
| `forget-all` | Delete all your notes |

### API Keys
| Command | What it does |
|---|---|
| `apikey-slot <1\|2\|3>` | Select Gemini API key slot |
| `apikey-groq [key]` | Set your Groq API key |
| `apikey-openrouter [key]` | Set your OpenRouter API key |

### Server / Debug
| Command | What it does |
|---|---|
| `ping` | Ping server + test AI client |
| `health` | Server health + knowledge stats |
| `stats` | Your stats (model, API key status) |
| `clock` | Ask server for the current time |
| `debug [on\|off]` | Toggle server debug output |
| `help` | Show the full command list |
| `exit` / `quit` | Logout and exit |

---

## Server Password Setup

Add `server_config.py` to your `flaskcode-server/` directory and patch
`server.py` per `PATCH_INSTRUCTIONS.py`.

Then edit `.conf/server_config`:
```
# Password max characters: 10
?password:mySecret

# Encrypt connection?
?True:true
# Valid Encryption: SHA256, SHA1, BASE64
?EncryptionMethod:SHA256
```

The client automatically reads the encryption method from the server
and hashes your `--pass` value accordingly before sending it.

---

## License

MIT — No Rights Reserved.

import re
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.path.join(BASE_DIR, "outputs")

EXT_MAP = {
    "python": "py", "py": "py",
    "javascript": "js", "js": "js", "node": "js",
    "typescript": "ts", "ts": "ts",
    "java": "java",
    "kotlin": "kt", "kt": "kt", "kts": "kts",
    "c": "c",
    "cpp": "cpp", "c++": "cpp", "cxx": "cpp",
    "csharp": "cs", "cs": "cs", "c#": "cs",
    "html": "html", "htm": "html",
    "css": "css",
    "json": "json",
    "yaml": "yaml", "yml": "yaml",
    "bash": "sh", "sh": "sh", "shell": "sh", "shellscript": "sh", "powershell": "ps1", "ps1": "ps1",
    "sql": "sql",
    "xml": "xml",
    "markdown": "md", "md": "md",
    "go": "go", "golang": "go",
    "rust": "rs", "rs": "rs",
    "php": "php",
    "ruby": "rb", "rb": "rb",
    "swift": "swift",
    "txt": "txt", "text": "txt", "plaintext": "txt", "plain": "txt",
}

# AI is prompted to open code blocks with: # --FileName myfile.ext --gen
FILENAME_DIRECTIVE = re.compile(r'^.*?--FileName\s+%?([^%\n]+?)%?\s*--gen.*?$\n?', re.MULTILINE)


def _resolve_extension(language):
    """Map a fenced-block language tag (e.g. 'python', 'javascript') to a real file extension."""
    lang = (language or "txt").strip().lower()
    if lang in EXT_MAP:
        return EXT_MAP[lang]
    return lang if lang.isalnum() and len(lang) <= 5 else "txt"


def strip_filename_directives(text):
    """Remove --FileName ... --gen directive lines from text, for clean display to the user."""
    return FILENAME_DIRECTIVE.sub('', text)


def resolve_extension(language):
    """Public wrapper around _resolve_extension, for callers outside this module."""
    return _resolve_extension(language)


# ---------------------------------------------------------------------------
# Action directives (v2)
#
# The AI can lead a fenced code block with one of several special comment
# lines (always the first non-blank line inside the fence, using '#' even
# in languages that don't normally comment with it):
#
#   0. Ask the user first what is their preferred CLI: Bash, PWSH,
#      WindowsPowerShell, or CMD. Use that answer to choose the correct
#      executor directive form.
#
#   1. Run a shell command and request permission before executing it:
#        # --cmd.exe -c"<command>" -ask
#        # --powershell.exe -c"<command>" -ask
#        # --pwsh.exe -c"<command>" -ask
#        # --bash -c"<command>" -ask
#        # --bash.exe -c"<command>" -ask
#      Optionally append -path"<working directory>" if the command should
#      run in a specific folder.
#
#   2. Write a file directly (only when the user actually wants a real file,
#      not just a snippet to look at):
#        # --FileName <filename.ext> -gen -write
#      followed by the file's full contents as the rest of the block.
#
#   3. Read an existing file from anywhere on disk:
#        # --FileName <label.ext> -rd -path"<full path>"
#      The user must approve before the file is opened.
#
# Any fenced block with no directive line at all is just illustrative code;
# the terminal will offer to save it rather than doing so automatically.
# ---------------------------------------------------------------------------

CODE_BLOCK_RE = re.compile(r'```(\w+)?\n(.*?)\n```', re.DOTALL)
SHELL_DIRECTIVE_RE = re.compile(r'--(?P<executor>pwsh\.exe|powershell\.exe|cmd\.exe|bash(?:\.exe)?)\s+-c"(?P<command>[^"]*)"(?P<flags>[^\n]*)')
FILENAME_V2_RE = re.compile(r'--FileName\s+%?(?P<filename>[^%\s]+)%?\s*(?P<flags>[^\n]*)')
PATH_FLAG_RE = re.compile(r'-path"(?P<path>[^"]*)"')


def _leading_directive(code):
    """Peel a single leading '# --pwsh.exe ...' / '# --FileName ...' comment
    line off the top of a code block (blank lines before it are skipped).
    Returns (directive_line_or_None, body_start_index) where body_start_index
    is the line index the remaining code body starts at."""
    lines = code.split('\n')
    for idx, line in enumerate(lines[:5]):
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith('#') and ('--FileName' in stripped or any(exec_name in stripped for exec_name in ('--pwsh.exe', '--powershell.exe', '--cmd.exe', '--bash', '--bash.exe'))):
            return stripped, idx + 1
        break
    return None, 0


def classify_blocks(text):
    """
    Parse every fenced code block in `text` and classify it by its leading
    action directive (if any). Returns a list of dicts, each with a 'kind'
    key: 'run' | 'write' | 'read' | 'plain'.

      run:   {"kind": "run", "language", "command", "cwd" (or None), "code"}
      write: {"kind": "write", "language", "filename", "code" (body only)}
      read:  {"kind": "read", "language", "filename", "path", "code"}
      plain: {"kind": "plain", "language", "code"}
    """
    blocks = []
    for lang, raw_code in CODE_BLOCK_RE.findall(text):
        language = lang if lang else "txt"
        code = raw_code.strip()
        directive, body_start = _leading_directive(code)
        body = '\n'.join(code.split('\n')[body_start:]).strip()

        if directive:
            m = SHELL_DIRECTIVE_RE.search(directive)
            if m:
                flags = m.group('flags') or ''
                path_m = PATH_FLAG_RE.search(flags)
                blocks.append({
                    "kind": "run",
                    "language": language,
                    "command": m.group('command'),
                    "executor": m.group('executor'),
                    "cwd": path_m.group('path') if path_m else None,
                    "code": code,
                    "directive": directive,
                })
                continue

        if directive and '--FileName' in directive:
            m = FILENAME_V2_RE.search(directive)
            if m:
                flags = (m.group('flags') or '').split()
                filename = m.group('filename')
                if '-rd' in flags:
                    path_m = PATH_FLAG_RE.search(m.group('flags') or '')
                    blocks.append({
                        "kind": "read",
                        "language": language,
                        "filename": filename,
                        "path": path_m.group('path') if path_m else None,
                        "code": code,
                        "directive": directive,
                    })
                    continue
                if '-write' in flags:
                    blocks.append({
                        "kind": "write",
                        "language": language,
                        "filename": filename,
                        "code": body,
                        "directive": directive,
                    })
                    continue

        blocks.append({
            "kind": "plain",
            "language": language,
            "code": code,
            "directive": directive,
        })

    return blocks


def strip_action_directives(text):
    """Remove leading action-directive comment lines from every fenced code
    block, for clean display to the user. Unlike strip_filename_directives,
    this understands the full v2 grammar (pwsh / write / read)."""
    def _clean(match):
        lang = match.group(1) or ''
        code = match.group(2).strip()
        directive, body_start = _leading_directive(code)
        if directive is None:
            cleaned = code
        else:
            cleaned = '\n'.join(code.split('\n')[body_start:]).strip()
        fence_lang = lang if lang else ''
        return f'```{fence_lang}\n{cleaned}\n```'

    return CODE_BLOCK_RE.sub(_clean, text)


def extract_code_blocks(text):
    """Extract all code blocks from text. Returns list of dicts with language/code/filename."""
    # Match ```language\ncode\n```
    pattern = r'```(\w+)?\n(.*?)\n```'
    matches = re.findall(pattern, text, re.DOTALL)

    code_blocks = []
    for lang, code in matches:
        language = lang if lang else "txt"
        code = code.strip()

        # Look for an explicit filename the AI left at the top of the block
        directive_match = FILENAME_DIRECTIVE.search(code)
        filename = None
        if directive_match:
            filename = directive_match.group(1).strip()
            code = FILENAME_DIRECTIVE.sub('', code, count=1).strip()

        if not filename:
            filename = f"generated_code.{_resolve_extension(language)}"

        code_blocks.append({
            'language': language,
            'code': code,
            'filename': filename
        })

    return code_blocks

def save_code_block(language, code, filename=None):
    """Save a code block to a file."""
    if not filename:
        filename = f"generated_code.{_resolve_extension(language)}"
    
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    output_path = os.path.join(OUTPUT_DIR, filename)
    
    try:
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(code)
        return True, f"Code saved: {output_path}"
    except Exception as e:
        return False, f"Error saving code: {e}"

def auto_save_code_blocks(response_text):
    """Automatically extract and save all code blocks from AI response."""
    blocks = extract_code_blocks(response_text)
    
    if not blocks:
        return 0, []
    
    saved = []
    used_names = set()
    for block in blocks:
        filename = block['filename']

        # Only disambiguate when two blocks actually land on the same name
        # (e.g. both fell back to generated_code.py with no directive)
        if filename in used_names:
            if '.' in filename:
                name, ext = filename.rsplit('.', 1)
            else:
                name, ext = filename, 'txt'
            counter = 2
            while f"{name}_{counter}.{ext}" in used_names:
                counter += 1
            filename = f"{name}_{counter}.{ext}"

        used_names.add(filename)

        success, msg = save_code_block(block['language'], block['code'], filename)
        if success:
            saved.append(filename)
    
    return len(saved), saved

if __name__ == "__main__":
    test_response = """
Here's a Python example:

```python
# --FileName hello_world.py --gen
def hello():
    print("Hello, World!")

hello()
```

And here's JavaScript with no directive (should fall back to .js, not .javascript):

```javascript
function hello() {
    console.log("Hello, World!");
}
hello();
```
"""
    
    count, files = auto_save_code_blocks(test_response)
    print(f"Saved {count} code blocks: {files}")
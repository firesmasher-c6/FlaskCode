import re
import sys
import time

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
BG_DARK = "\033[40m"
BG_GRAY = "\033[100m"

# Animation frames
LOAD_FRAMES = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
PULSE_FRAMES = ["◐", "◓", "◑", "◒"]
ARROW_FRAMES = ["→", "⇢", "➤", "▶"]
WAVE_FRAMES = ["∿ ", "≈ ", "∾ "]

KEYWORDS = {
    "python": ["def", "class", "if", "else", "elif", "for", "while", "return", "import", "from", "try", "except", "finally", "with", "as", "lambda", "yield", "async", "await", "True", "False", "None", "and", "or", "not", "is", "in", "del", "pass", "raise", "assert", "global", "nonlocal"],
    "java": ["public", "private", "protected", "static", "final", "abstract", "class", "interface", "extends", "implements", "new", "return", "if", "else", "for", "while", "do", "switch", "case", "break", "continue", "try", "catch", "finally", "throw", "throws", "void", "int", "boolean", "String", "double", "float", "long"],
    "javascript": ["function", "const", "let", "var", "return", "if", "else", "for", "while", "do", "switch", "case", "break", "continue", "try", "catch", "finally", "async", "await", "class", "extends", "new", "this", "super", "import", "export", "from", "as", "typeof", "instanceof", "delete", "void"],
    "typescript": ["function", "const", "let", "var", "return", "if", "else", "for", "while", "do", "switch", "case", "break", "continue", "try", "catch", "finally", "async", "await", "class", "extends", "new", "this", "super", "import", "export", "from", "as", "type", "interface", "enum", "namespace", "public", "private", "protected"],
    "cpp": ["int", "void", "return", "if", "else", "for", "while", "do", "switch", "case", "class", "struct", "public", "private", "protected", "static", "const", "virtual", "try", "catch", "throw", "namespace", "using", "template", "typename", "bool", "char", "float", "double"],
    "sql": ["SELECT", "FROM", "WHERE", "JOIN", "LEFT", "RIGHT", "INNER", "OUTER", "ON", "INSERT", "UPDATE", "DELETE", "CREATE", "DROP", "ALTER", "TABLE", "DATABASE", "INDEX", "VIEW", "AND", "OR", "NOT", "IN", "EXISTS", "BETWEEN", "LIKE", "ORDER", "BY", "GROUP", "HAVING", "AS", "DISTINCT"],
    "html": ["html", "head", "body", "div", "span", "p", "a", "img", "script", "style", "title", "meta", "link", "button", "input", "form", "table", "tr", "td", "th", "h1", "h2", "h3", "section", "article", "nav", "footer"],
    "bash": ["if", "then", "else", "elif", "fi", "for", "while", "do", "done", "case", "esac", "function", "return", "export", "cd", "echo", "exit"],
    "powershell": ["if", "else", "elseif", "switch", "for", "foreach", "while", "do", "function", "return", "param", "Write-Host", "Write-Output", "$_", "Get-", "Set-"],
}

BUILTINS = {
    "python": ["print", "len", "range", "str", "int", "float", "list", "dict", "set", "tuple", "open", "map", "filter", "zip", "enumerate", "isinstance", "type"],
    "java": ["System", "out", "println", "main", "new", "ArrayList", "HashMap", "String"],
    "javascript": ["console", "log", "document", "window", "fetch", "JSON", "Array", "Object", "Math"],
    "typescript": ["console", "log", "document", "window", "fetch", "JSON", "Array", "Object", "interface", "type"],
    "cpp": ["cout", "cin", "std", "vector", "string", "pair", "map", "set"],
    "sql": ["COUNT", "SUM", "AVG", "MAX", "MIN", "DISTINCT"],
    "bash": ["echo", "cd", "ls", "grep", "sed", "awk", "find"],
    "powershell": ["Write-Host", "Write-Output", "Get-Item", "Set-Location", "Write-Error"],
}

def _animate_text(text: str, delay: float = 0.01) -> None:
    """Print text with character-by-character animation."""
    for char in text:
        sys.stdout.write(char)
        sys.stdout.flush()
        time.sleep(delay)
    sys.stdout.write('\n')

def _highlight_code(code: str, language: str = "python") -> str:
    lang = language.lower().strip()
    keywords = KEYWORDS.get(lang, KEYWORDS.get("python", []))
    builtins = BUILTINS.get(lang, [])
    
    highlighted = code
    
    # Highlight keywords
    for keyword in keywords:
        pattern = r'\b' + re.escape(keyword) + r'\b'
        highlighted = re.sub(pattern, f"{MAGENTA}{BOLD}{keyword}{RESET}", highlighted, flags=re.IGNORECASE)
    
    # Highlight builtins
    for builtin in builtins:
        pattern = r'\b' + re.escape(builtin) + r'\b'
        highlighted = re.sub(pattern, f"{GREEN}{builtin}{RESET}", highlighted, flags=re.IGNORECASE)
    
    # Highlight strings (double and single quotes)
    highlighted = re.sub(r'("(?:\\.|[^"\\])*")', f'{YELLOW}{ITALIC}\\1{RESET}', highlighted)
    highlighted = re.sub(r"('(?:\\.|[^'\\])*')", f'{YELLOW}{ITALIC}\\1{RESET}', highlighted)
    
    # Highlight numbers
    highlighted = re.sub(r'\b(\d+\.?\d*)\b', f'{CYAN}\\1{RESET}', highlighted)
    
    # Highlight comments (# for Python, // for JS/C++, -- for SQL)
    highlighted = re.sub(r'(#.*?)$', f'{DIM}{GRAY}\\1{RESET}', highlighted, flags=re.MULTILINE)
    highlighted = re.sub(r'(//.*?)$', f'{DIM}{GRAY}\\1{RESET}', highlighted, flags=re.MULTILINE)
    highlighted = re.sub(r'(--.*?)$', f'{DIM}{GRAY}\\1{RESET}', highlighted, flags=re.MULTILINE)
    
    # Highlight operators
    highlighted = re.sub(r'([+\-*/%=!<>&|^~])', f'{RED}\\1{RESET}', highlighted)
    
    return highlighted

def _format_code_block(lang: str, code: str) -> str:
    """Format a code block with language label and borders."""
    highlighted = _highlight_code(code, lang)
    
    # Create a nice border with language label
    lang_label = lang.upper()
    border_width = 56
    lang_space = border_width - len(lang_label) - 6
    border_top = f"{GRAY}┌─ {BOLD}{CYAN}{lang_label}{RESET}{GRAY} {CYAN}{'─' * max(1, lang_space)}{GRAY}─┐{RESET}"
    border_bottom = f"{GRAY}└{'─' * (border_width - 2)}┘{RESET}"
    
    return f"\n{border_top}\n{highlighted}\n{border_bottom}\n"

def format_response(text: str, animate: bool = False) -> str:
    result = text
    
    # Process code blocks with syntax highlighting
    def wrap_code(match):
        lang = match.group(1) or "python"
        code = match.group(2).strip()
        return _format_code_block(lang, code)
    
    # Match ``` lang \n code \n ```
    result = re.sub(r'```(\w+)?\n(.*?)\n```', wrap_code, result, flags=re.DOTALL)
    
    # Inline code (single backtick) - enhanced with background
    result = re.sub(r'`([^`]+)`', f'{BG_DARK}{CYAN} \\1 {RESET}', result)
    
    # Headers (# text)
    result = re.sub(r'^(#{1,6})\s+(.+?)$', lambda m: f'{CYAN}{BOLD}{m.group(1)} {m.group(2)}{RESET}', result, flags=re.MULTILINE)
    
    # Bold **text**
    result = re.sub(r'\*\*([^*]+)\*\*', f'{YELLOW}{BOLD}\\1{RESET}', result)
    result = re.sub(r'__([^_]+)__', f'{YELLOW}{BOLD}\\1{RESET}', result)
    
    # Italic *text* (but not inside **)
    result = re.sub(r'(?<!\*)\*(?!\*)([^*]+?)\*(?!\*)', f'{CYAN}{ITALIC}\\1{RESET}', result)
    result = re.sub(r'(?<!_)_(?!_)([^_]+?)_(?!_)', f'{CYAN}{ITALIC}\\1{RESET}', result)
    
    # Lists (- or * at start of line)
    result = re.sub(r'^([*\-])\s+(.+?)$', f'{GREEN}{BOLD}\\1{RESET} \\2', result, flags=re.MULTILINE)
    
    # Links [text](url)
    result = re.sub(r'\[([^\]]+)\]\(([^\)]+)\)', f'{BLUE}{UNDERLINE}[\\1]{RESET}{DIM} ➜ \\2{RESET}', result)
    
    # Blockquotes (>)
    result = re.sub(r'^>\s+(.+?)$', f'{GRAY}{ITALIC}❝ \\1{RESET}', result, flags=re.MULTILINE)
    
    return result
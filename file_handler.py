import os
import shutil
import base64
from pathlib import Path

ALLOWED_EXTENSIONS = {
    '.png', '.svg', '.txt', '.md', '.html', '.css', '.js', '.py',
    '.java', '.c', '.cpp', '.cs', '.ts', '.json', '.kt', '.kts',
    '.sh', '.yaml', '.yml', '.toml', '.ini', '.cfg', '.xml', '.sql',
}

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Linux-friendly input dirs — editable by the operator
INPUT_DIRS = [
    os.path.expanduser("~/Documents"),
    os.path.expanduser("~/Downloads"),
    os.path.join(BASE_DIR, "inputs"),   # local project inputs folder
]

OUTPUT_DIR = os.path.join(BASE_DIR, "outputs")


def get_allowed_files():
    files = []
    for input_dir in INPUT_DIRS:
        if not os.path.exists(input_dir):
            continue
        for root, dirs, filenames in os.walk(input_dir):
            # skip hidden dirs
            dirs[:] = [d for d in dirs if not d.startswith('.')]
            for filename in filenames:
                ext = Path(filename).suffix.lower()
                if ext in ALLOWED_EXTENSIONS:
                    full_path = os.path.join(root, filename)
                    files.append({
                        'name': filename,
                        'path': full_path,
                        'ext': ext,
                        'dir': os.path.dirname(full_path),
                    })
    return files


def read_file(file_path):
    ext = Path(file_path).suffix.lower()
    if ext in {'.png', '.svg'}:
        with open(file_path, 'rb') as f:
            content = base64.b64encode(f.read()).decode('utf-8')
        return content, True
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        return content, False
    except UnicodeDecodeError:
        with open(file_path, 'rb') as f:
            content = base64.b64encode(f.read()).decode('utf-8')
        return content, True


def write_file(filename, content, is_binary=False):
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    output_path = os.path.join(OUTPUT_DIR, filename)
    try:
        if is_binary:
            with open(output_path, 'wb') as f:
                f.write(base64.b64decode(content))
        else:
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(content)
        return True, f"File saved: {output_path}"
    except Exception as e:
        return False, f"Error saving file: {e}"


def clear_outputs():
    if not os.path.exists(OUTPUT_DIR):
        return True, "outputs/ is already empty (folder doesn't exist yet)"
    removed = 0
    errors = []
    for entry in os.listdir(OUTPUT_DIR):
        entry_path = os.path.join(OUTPUT_DIR, entry)
        try:
            if os.path.isfile(entry_path) or os.path.islink(entry_path):
                os.remove(entry_path)
            else:
                shutil.rmtree(entry_path)
            removed += 1
        except Exception as e:
            errors.append(f"{entry}: {e}")
    msg = f"Cleared {removed} item(s) from outputs/"
    if errors:
        msg += f" ({len(errors)} error(s): {'; '.join(errors)})"
        return False, msg
    return True, msg


def format_file_for_ai(file_path, file_content, is_binary):
    filename = os.path.basename(file_path)
    ext = Path(file_path).suffix.lower()
    if is_binary:
        return f"[BINARY FILE: {filename}]\nBase64 Content:\n{file_content}"
    return f"[FILE: {filename}]\n```{ext[1:]}\n{file_content}\n```"


def list_available_files():
    files = get_allowed_files()
    return files


def get_file_by_name(filename):
    files = get_allowed_files()
    for f in files:
        if f['name'] == filename:
            return f['path']
    return None


def process_file_for_ai(filename):
    file_path = get_file_by_name(filename)
    if not file_path:
        return None, f"File not found: {filename}"
    content, is_binary = read_file(file_path)
    formatted = format_file_for_ai(file_path, content, is_binary)
    return formatted, None


def read_filepath_for_ai(filepath):
    if not filepath:
        return None, "No filepath provided"
    if not os.path.isfile(filepath):
        return None, f"File not found: {filepath}"
    ext = Path(filepath).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        return None, f"File type not allowed: {ext or '(no extension)'}"
    try:
        content, is_binary = read_file(filepath)
    except Exception as e:
        return None, f"Error reading file: {e}"
    formatted = format_file_for_ai(filepath, content, is_binary)
    return formatted, None

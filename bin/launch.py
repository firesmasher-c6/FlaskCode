import subprocess
import sys

try:
    subprocess.Popen([
        "wt",
        "-p", "Flask Code"
    ])
except FileNotFoundError:
    print("Error: Windows Terminal not found. Make sure 'wt' is in your PATH.")
    sys.exit(1)
except Exception as e:
    print(f"Error launching Windows Terminal: {e}")
    sys.exit(1)
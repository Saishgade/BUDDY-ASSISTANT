from __future__ import annotations

import os
import sys
import webbrowser
from pathlib import Path

ROOT = Path(__file__).resolve().parent
APP_FILE = ROOT / "app.py"

if __name__ == "__main__":
    print("Buddy mobile companion app scaffold ready.")
    print(f"Open the generated app UI from: {APP_FILE}")

from __future__ import annotations

import json
import os
import sys
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def read_pairing_code() -> str:
    return os.environ.get("BUDDY_MOBILE_PAIR_CODE", "0000")


def read_pairing_token() -> str:
    return os.environ.get("BUDDY_MOBILE_PAIR_TOKEN", "")


def build_ui() -> str:
    code = read_pairing_code()
    return f"""
<!doctype html>
<html>
<head>
  <meta charset=\"utf-8\" />
  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />
  <title>Buddy Mobile App</title>
  <style>
    body {{ font-family: Arial, sans-serif; background: #07131e; color: white; margin: 0; padding: 20px; }}
    .card {{ max-width: 480px; margin: 0 auto; background: #112235; border-radius: 16px; padding: 24px; }}
    .pill {{ display:inline-block; background:#1d4d64; padding:6px 10px; border-radius:999px; font-size:12px; margin-bottom:12px; }}
    h1 {{ margin-top: 0; }}
    .code {{ font-size: 36px; font-weight: bold; letter-spacing: 4px; margin: 18px 0; }}
    button {{ width: 100%; padding: 12px; border: none; border-radius: 10px; background: #2fa4d8; color: white; font-weight: bold; }}
    .status {{ margin-top: 12px; color: #a8d8ec; }}
  </style>
</head>
<body>
  <div class=\"card\">
    <div class=\"pill\">Dedicated companion app</div>
    <h1>Buddy Mobile</h1>
    <p>Pair with your PC using the code below.</p>
    <div class=\"code\">{code}</div>
    <button onclick=\"pairNow()\">Pair with PC</button>
    <div class=\"status\" id=\"status\">Waiting for pairing.</div>
  </div>
  <script>
    function pairNow() {{
      const status = document.getElementById('status');
      status.textContent = 'Pairing request sent...';
      fetch('/pair?code=' + encodeURIComponent('{code}'))
        .then(r => r.json())
        .then(d => {{ status.textContent = d.message || 'Paired.'; }})
        .catch(err => {{ status.textContent = 'Pairing failed: ' + err.message; }});
    }}
  </script>
</body>
</html>
"""


def main() -> None:
    html = build_ui()
    print(html)


if __name__ == "__main__":
    main()

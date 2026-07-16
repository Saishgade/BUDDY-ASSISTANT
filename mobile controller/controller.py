from __future__ import annotations

import base64
import hashlib
import io
import json
import os
import platform
import random
import re
import socket
import subprocess
import sys
import threading
import time
import urllib.parse
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Dict, Optional

try:
    import qrcode
except Exception:  # pragma: no cover
    qrcode = None


# Shared process-wide state so repeated reloads keep the same server and queue.
def _shared_state() -> Dict[str, Any]:
    if not hasattr(sys, "_buddy_mobile_state"):
        sys._buddy_mobile_state = {
            "server": None,
            "queue": [],
            "queue_lock": threading.Lock(),
            "server_lock": threading.Lock(),
        }
    return sys._buddy_mobile_state


def _state_file_path() -> Path:
    custom_path = os.environ.get("BUDDY_MOBILE_STATE_FILE", "")
    if custom_path:
        return Path(custom_path)
    return Path.home() / ".buddy" / "mobile_state.json"


def _migrate_state_file(path: Path) -> None:
    if path.exists() or not path.parent.exists():
        return
    legacy_path = Path(__file__).resolve().parent / "mobile_state.json"
    if legacy_path.exists():
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(legacy_path.read_text(encoding="utf-8"), encoding="utf-8")
        except Exception:
            pass


def _load_persisted_state() -> Dict[str, Any]:
    path = _state_file_path()
    _migrate_state_file(path)
    if not path.exists():
        return {"connected": False, "pair_code": "", "pair_token": "", "queue": []}
    try:
        with path.open("r", encoding="utf-8") as fh:
            data = json.load(fh)
            if isinstance(data, dict):
                data.setdefault("connected", False)
                data.setdefault("pair_code", "")
                data.setdefault("pair_token", "")
                data.setdefault("queue", [])
                return data
    except Exception:
        pass
    return {"connected": False, "pair_code": "", "pair_token": "", "queue": []}


def _save_persisted_state(state: Dict[str, Any]) -> None:
    path = _state_file_path()
    _migrate_state_file(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        json.dump(state, fh, indent=2)


def _read_queue() -> list[Dict[str, Any]]:
    state = _load_persisted_state()
    queue = state.get("queue") or []
    if not isinstance(queue, list):
        return []
    return queue


def _write_queue(queue: list[Dict[str, Any]]) -> None:
    state = _load_persisted_state()
    state["queue"] = queue
    _save_persisted_state(state)


def _enqueue_command(action: str, target: str, value: str, metadata: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    state = _shared_state()
    command = {
        "id": base64.urlsafe_b64encode(os.urandom(6)).decode("ascii").rstrip("="),
        "action": action,
        "target": target,
        "value": value,
        "metadata": metadata or {},
        "created_at": time.time(),
    }
    with state["queue_lock"]:
        state["queue"].append(command)
        queue = list(state["queue"])
    persisted = _load_persisted_state()
    persisted.setdefault("queue", [])
    persisted["queue"] = queue
    _save_persisted_state(persisted)
    return command


def _pop_next_command() -> Optional[Dict[str, Any]]:
    state = _shared_state()
    with state["queue_lock"]:
        if state["queue"]:
            command = state["queue"].pop(0)
            queue = list(state["queue"])
        else:
            queue = list(state["queue"])
            command = None
    if command is not None:
        persisted = _load_persisted_state()
        persisted["queue"] = queue
        _save_persisted_state(persisted)
    return command


def _is_connected() -> bool:
    env_value = os.environ.get("BUDDY_MOBILE_CONNECTED", "").strip().lower()
    if env_value in {"1", "true", "yes", "on"}:
        return True
    if env_value in {"0", "false", "no", "off", ""} and "BUDDY_MOBILE_CONNECTED" in os.environ:
        return False
    state = _load_persisted_state()
    return bool(state.get("connected"))


class LocalPairingServer:
    """Local pairing and command endpoint for phone-to-PC control."""

    def __init__(self, host: str = "127.0.0.1", port: int = 8765) -> None:
        self.host = host
        self.port = port
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._httpd: Optional[ThreadingHTTPServer] = None

    def is_running(self) -> bool:
        return bool(self._thread and self._thread.is_alive())

    def _json_response(self, handler: BaseHTTPRequestHandler, status: int, payload: Dict[str, Any]) -> None:
        body = json.dumps(payload).encode("utf-8")
        handler.send_response(status)
        # allow mobile clients to call local endpoints without CORS issues
        handler.send_header("Access-Control-Allow-Origin", "*")
        handler.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        handler.send_header("Access-Control-Allow-Headers", "Content-Type")
        handler.send_header("Content-Type", "application/json")
        handler.send_header("Content-Length", str(len(body)))
        handler.end_headers()
        handler.wfile.write(body)

    def _accept_pairing(self, code: str, token: str) -> Dict[str, Any]:
        persisted = _load_persisted_state()
        expected_code = os.environ.get("BUDDY_MOBILE_PAIR_CODE", "") or str(persisted.get("pair_code", "")).strip()
        expected_token = os.environ.get("BUDDY_MOBILE_PAIR_TOKEN", "") or str(persisted.get("pair_token", "")).strip()
        if not code and not token:
            persisted.setdefault("connected", False)
            _save_persisted_state(persisted)
            return {"ok": True, "message": "Mobile companion is listening."}
        if code and code == expected_code and (not token or token == expected_token or token == ""):
            os.environ["BUDDY_MOBILE_CONNECTED"] = "1"
            persisted["connected"] = True
            persisted["pair_code"] = code
            persisted["pair_token"] = token
            _save_persisted_state(persisted)
            return {"ok": True, "message": "Pairing accepted."}
        return {"ok": False, "message": "Invalid or expired pairing code."}

    def _make_handler(self):
        server_ref = self

        class PairingRequestHandler(BaseHTTPRequestHandler):
            def do_GET(self) -> None:  # noqa: N802
                try:
                    parsed = urllib.parse.urlparse(self.path)
                    # normalize path to tolerate trailing slashes
                    path = (parsed.path or "/").rstrip('/') or '/'
                    query = urllib.parse.parse_qs(parsed.query)
                    code = (query.get("code", [""])[0] or "").strip()
                    token = (query.get("token", [""])[0] or "").strip()

                    # log minimal request info for debugging
                    try:
                        print(f"HTTP GET from {self.client_address[0]} {path}")
                    except Exception:
                        pass

                    if path in {"/pair", "/connect"}:
                        result = server_ref._accept_pairing(code, token)
                        status = HTTPStatus.OK if result.get("ok") else HTTPStatus.BAD_REQUEST
                        server_ref._json_response(self, status, result)
                        return

                    if path == "/pair-info":
                        controller = MobileController()
                        info = controller.get_pairing_info()
                        server_ref._json_response(
                            self,
                            HTTPStatus.OK,
                            {
                                "ok": True,
                                "pair_code": info["pair_code"],
                                "token": os.environ.get("BUDDY_MOBILE_PAIR_TOKEN", ""),
                                "expires_at": info["expires_at"],
                                "connect_url": info["connect_url"],
                                "challenge": info["challenge"],
                            },
                        )
                        return

                    if path == "/commands/next":
                        if not _is_connected():
                            server_ref._json_response(self, HTTPStatus.UNAUTHORIZED, {"ok": False, "message": "Not paired yet."})
                            return
                        command = _pop_next_command()
                        server_ref._json_response(self, HTTPStatus.OK, {"ok": True, "command": command})
                        return

                    if path == "/queue":
                        # Return both in-memory and persisted queues for debugging
                        state = _shared_state()
                        persisted = _load_persisted_state()
                        server_ref._json_response(self, HTTPStatus.OK, {"ok": True, "in_memory_queue": state.get("queue", []), "persisted_queue": persisted.get("queue", [])})
                        return

                    server_ref._json_response(self, HTTPStatus.NOT_FOUND, {"ok": False, "message": "Not found."})
                except Exception as exc:  # catch handler errors and return JSON
                    server_ref._json_response(self, HTTPStatus.INTERNAL_SERVER_ERROR, {"ok": False, "message": f"Server error: {str(exc)}"})
                    return

            def do_POST(self) -> None:  # noqa: N802
                try:
                    # Support OPTIONS preflight
                    if self.command == "OPTIONS":
                        self.send_response(HTTPStatus.NO_CONTENT)
                        self.send_header("Access-Control-Allow-Origin", "*")
                        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
                        self.send_header("Access-Control-Allow-Headers", "Content-Type")
                        self.end_headers()
                        return

                    length = int(self.headers.get("Content-Length", "0"))
                    body = self.rfile.read(length) if length else b"{}"
                    try:
                        payload = json.loads(body.decode("utf-8") or "{}")
                    except Exception:
                        payload = {}
                    try:
                        print(f"HTTP POST from {self.client_address[0]} {self.path} payload={str(payload)[:200]}")
                    except Exception:
                        pass
                    result = server_ref.handle_command_request(payload)
                    server_ref._json_response(self, HTTPStatus.OK if result.get("ok") else HTTPStatus.BAD_REQUEST, result)
                except Exception as exc:
                    server_ref._json_response(self, HTTPStatus.INTERNAL_SERVER_ERROR, {"ok": False, "message": f"Server error: {str(exc)}"})
                    return

            def log_message(self, format: str, *args: Any) -> None:  # noqa: A003
                return

        return PairingRequestHandler

    def handle_command_request(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        action = str(payload.get("action", "")).strip().lower()
        target = str(payload.get("target", "")).strip()
        value = str(payload.get("value", "")).strip()
        metadata = payload.get("metadata") or {}

        if not self.validate(os.environ.get("BUDDY_MOBILE_PAIR_CODE", ""), os.environ.get("BUDDY_MOBILE_PAIR_TOKEN", "")) and not _is_connected():
            return {"ok": False, "message": "Pairing required before sending commands."}

        if not action:
            return {"ok": False, "message": "No action supplied."}

        controller = MobileController()
        if action == "complete_pairing":
            code = str(payload.get("pair_code", "")).strip()
            token = str(payload.get("pair_token", "")).strip()
            return controller.complete_pairing(code, token)

        command_result = controller.execute(action, target=target, value=value, metadata=metadata)
        return {
            "ok": True,
            "message": command_result,
            "action": action,
            "target": target,
            "value": value,
        }

    def start(self) -> None:
        if self.is_running():
            return

        self._stop_event.clear()

        def _serve() -> None:
            try:
                self._httpd = ThreadingHTTPServer((self.host, self.port), self._make_handler())
            except OSError:
                return
            self._httpd.timeout = 0.5
            try:
                while not self._stop_event.is_set():
                    self._httpd.handle_request()
            finally:
                if self._httpd is not None:
                    self._httpd.server_close()
                    self._httpd = None

        self._thread = threading.Thread(target=_serve, daemon=True)
        self._thread.start()
        time.sleep(0.05)

    def stop(self) -> None:
        self._stop_event.set()
        if self._httpd is not None:
            try:
                self._httpd.shutdown()
            except Exception:
                pass
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=1)

    def build_response(self, code: str, token: str) -> Dict[str, Any]:
        return {
            "ok": True,
            "local_only": True,
            "one_time": True,
            "pair_code": code,
            "token": token,
            "message": "Pairing accepted on localhost.",
        }

    def validate(self, code: str, token: str) -> bool:
        env_code = os.environ.get("BUDDY_MOBILE_PAIR_CODE", "")
        env_token = os.environ.get("BUDDY_MOBILE_PAIR_TOKEN", "")
        env_expiry = int(os.environ.get("BUDDY_MOBILE_PAIR_EXPIRY", "0"))
        state = _load_persisted_state()
        now = int(time.time())
        if env_code and env_token and now < env_expiry:
            return code == env_code and token == env_token
        if state.get("connected"):
            saved_code = str(state.get("pair_code", ""))
            saved_token = str(state.get("pair_token", ""))
            return code == saved_code and token == saved_token
        return False


def _ensure_server_running(host: str, port: int = 8765) -> LocalPairingServer:
    state = _shared_state()
    with state["server_lock"]:
        server: Optional[LocalPairingServer] = state["server"]
        if server is None or not server.is_running():
            server = LocalPairingServer(host=host, port=port)
            server.start()
            state["server"] = server
        return server


class MobileController:
    """Controller for basic phone operations through a paired device bridge."""

    def __init__(self) -> None:
        self.platform_name = platform.system()

    def parse_command(self, text: str) -> Dict[str, Any]:
        raw = (text or "").strip()
        if not raw:
            return {"action": "", "target": "", "value": ""}

        query = raw.lower()

        if query.startswith("open ") or "open" in query:
            if "whatsapp" in query:
                return {"action": "open_app", "target": "whatsapp", "value": ""}
            if "telegram" in query:
                return {"action": "open_app", "target": "telegram", "value": ""}
            if "youtube" in query:
                return {"action": "open_app", "target": "youtube", "value": ""}
            if "spotify" in query:
                return {"action": "open_app", "target": "spotify", "value": ""}
            if "maps" in query:
                return {"action": "open_app", "target": "maps", "value": ""}
            if "chrome" in query:
                return {"action": "open_app", "target": "chrome", "value": ""}
            if "contacts" in query:
                return {"action": "open_app", "target": "contacts", "value": ""}

        if re.search(r"\bcall\b", query, flags=re.IGNORECASE):
            target = re.split(r"\bcall\b", raw, maxsplit=1, flags=re.IGNORECASE)[1].strip(" :")
            return {"action": "call", "target": target or "", "value": ""}

        if re.search(r"\bsend\b", query, flags=re.IGNORECASE) and "message" in query:
            platform = "telegram" if "telegram" in query else "whatsapp"
            message_text = raw.split(":", 1)[1].strip() if ":" in raw else ""
            return {"action": "send_message", "target": "", "value": message_text, "metadata": {"platform": platform}}

        if "note" in query or "notes" in query:
            note_text = raw.split(":", 1)[1].strip() if ":" in raw else ""
            return {"action": "make_note", "target": "", "value": note_text}

        if "play" in query or "music" in query:
            if "spotify" in query:
                return {"action": "play_media", "target": "spotify", "value": ""}
            if "youtube" in query:
                return {"action": "play_media", "target": "youtube", "value": ""}
            return {"action": "play_media", "target": "youtube", "value": ""}

        return {"action": "", "target": "", "value": ""}

    def get_local_ip(self) -> str:
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
                sock.connect(("8.8.8.8", 80))
                return sock.getsockname()[0]
        except Exception:
            try:
                return socket.gethostbyname(socket.gethostname())
            except Exception:
                return "127.0.0.1"

    def get_connection_status(self) -> Dict[str, Any]:
        connected = _is_connected()
        return {
            "connected": connected,
            "status": "CONNECTED" if connected else "DISCONNECTED",
            "label": "Mobile connected" if connected else "Mobile disconnected",
        }

    def get_pairing_info(self) -> Dict[str, Any]:
        code = os.environ.get("BUDDY_MOBILE_PAIR_CODE")
        if not code:
            code = f"{random.randint(1000, 9999)}"
            os.environ["BUDDY_MOBILE_PAIR_CODE"] = code
        host = self.get_local_ip()
        _ensure_server_running(host)
        expiry = int(time.time()) + 600
        token = hashlib.sha256(f"{code}:{expiry}".encode("utf-8")).hexdigest()[:24]
        challenge = base64.urlsafe_b64encode(os.urandom(12)).decode("ascii").rstrip("=")
        secret = base64.urlsafe_b64encode(os.urandom(16)).decode("ascii").rstrip("=")
        os.environ["BUDDY_MOBILE_PAIR_TOKEN"] = token
        os.environ["BUDDY_MOBILE_PAIR_EXPIRY"] = str(expiry)
        os.environ["BUDDY_MOBILE_PAIR_CHALLENGE"] = challenge
        os.environ["BUDDY_MOBILE_PAIR_SECRET"] = secret
        state = _load_persisted_state()
        state["pair_code"] = code
        state["pair_token"] = token
        state["connected"] = bool(state.get("connected"))
        _save_persisted_state(state)
        return {
            "pair_code": code,
            "host": host,
            "port": 8765,
            "connect_url": f"http://{host}:8765/connect?code={code}&token={token}",
            "instructions": "Open this local-only link on your phone and enter the code to pair securely.",
            "local_only": True,
            "one_time": True,
            "expires_at": expiry,
            "challenge": challenge,
            "secret_hint": "A random secret was generated for the handshake.",
        }

    def build_command(self, action: str, target: str = "", value: str = "", metadata: Optional[Dict[str, Any]] = None) -> str:
        metadata = metadata or {}
        action = (action or "").strip().lower()
        target = (target or "").strip()
        value = (value or "").strip()

        if action == "call":
            return f"tel:{urllib.parse.quote(target)}"

        if action == "sms":
            return f"smsto:{urllib.parse.quote(target)}?body={urllib.parse.quote(value)}"

        if action == "open_app":
            app_map = {
                "whatsapp": "com.whatsapp",
                "telegram": "org.telegram.messenger",
                "youtube": "com.google.android.youtube",
                "youtube music": "com.google.android.apps.youtube.music",
                "spotify": "com.spotify.music",
                "google keep": "com.google.android.keep",
                "keep": "com.google.android.keep",
                "contacts": "com.android.contacts",
                "chrome": "com.android.chrome",
                "maps": "com.google.android.apps.maps",
                "google maps": "com.google.android.apps.maps",
                "gmail": "com.google.android.gm",
                "phone": "com.android.dialer",
                "settings": "com.android.settings",
                "camera": "com.android.camera",
                "calculator": "com.android.calculator2",
            }
            package = app_map.get(target.lower(), target)
            if not package:
                return ""
            if str(package).startswith(("android-app://", "intent://", "http://", "https://", "whatsapp://", "tg://", "spotify://", "youtube://", "geo:", "googlechrome://")):
                return str(package)
            return f"intent://#Intent;package={package};S.browser_fallback_url=https://play.google.com/store/apps/details?id={package};end"

        if action == "play_media":
            service_urls = {
                "youtube": "https://www.youtube.com/results?search_query=",
                "youtubemusic": "https://music.youtube.com/search?q=",
                "spotify": "https://open.spotify.com/search/",
            }
            base = service_urls.get(target.lower(), "https://www.youtube.com/results?search_query=")
            query = urllib.parse.quote(value or target)
            return f"{base}{query}"

        if action == "make_note":
            note_text = urllib.parse.quote(value or "New note")
            return f"android-app://com.google.android.keep?note={note_text}"

        if action == "send_message":
            platform_name = (metadata.get("platform") or "whatsapp").strip().lower()
            payload = {
                "platform": platform_name,
                "target": target,
                "message": value,
            }
            return json.dumps(payload)

        return ""

    def execute(self, action: str, target: str = "", value: str = "", metadata: Optional[Dict[str, Any]] = None) -> str:
        metadata = metadata or {}
        if not _is_connected():
            _enqueue_command(action, target, value, metadata)
            return "No phone is paired right now - I queued it for as soon as one connects."

        _enqueue_command(action, target, value, metadata)
        return f"Sent to your phone: {action} {(target or value)}".strip()

    def complete_pairing(self, code: str, token: str) -> Dict[str, Any]:
        server = LocalPairingServer()
        if not server.validate(code, token):
            return {"ok": False, "message": "Pairing failed or expired."}
        os.environ["BUDDY_MOBILE_CONNECTED"] = "1"
        os.environ.pop("BUDDY_MOBILE_PAIR_TOKEN", None)
        os.environ.pop("BUDDY_MOBILE_PAIR_EXPIRY", None)
        state = _load_persisted_state()
        state["connected"] = True
        state["pair_code"] = code
        state["pair_token"] = token
        _save_persisted_state(state)
        _ensure_server_running(self.get_local_ip())
        return server.build_response(code, token)

    def start_local_server(self, host: Optional[str] = None) -> Dict[str, Any]:
        bind_host = host or "127.0.0.1"
        server = _ensure_server_running(bind_host)
        return {
            "ok": True,
            "host": bind_host,
            "port": server.port,
            "message": "Local companion server started.",
        }

    def get_companion_page(self) -> str:
        base_dir = Path(__file__).resolve().parent
        page_path = base_dir / "companion.html"
        if not page_path.exists():
            return ""
        return page_path.read_text(encoding="utf-8")

    def get_qr_payload(self) -> Dict[str, Any]:
        info = self.get_pairing_info()
        url = info.get("connect_url", "")
        if not url:
            return {"ok": False, "message": "No pairing URL available."}
        if qrcode is None:
            return {"ok": False, "message": "qrcode package is not installed."}
        img = qrcode.make(url)
        buffer = io.BytesIO()
        img.save(buffer, format="PNG")
        encoded = base64.b64encode(buffer.getvalue()).decode("ascii")
        return {
            "ok": True,
            "url": url,
            "image_base64": encoded,
            "mime": "image/png",
        }

    def wrap_command(self, command: Dict[str, Any]) -> Dict[str, Any]:
        secret = os.environ.get("BUDDY_MOBILE_PAIR_SECRET", "")
        if not secret:
            return {"ok": False, "message": "No active mobile secret."}
        payload = json.dumps(command, sort_keys=True).encode("utf-8")
        token = hashlib.sha256(payload + secret.encode("utf-8")).hexdigest()
        return {
            "ok": True,
            "payload": base64.urlsafe_b64encode(payload).decode("ascii"),
            "token": token,
        }


def mobile_controller(parameters=None, response=None, player=None, session_memory=None) -> str:
    params = parameters or {}
    action = str(params.get("action", "")).strip().lower()
    target = str(params.get("target", "")).strip()
    value = str(params.get("value", "")).strip()
    metadata = params.get("metadata") or {}
    controller = MobileController()

    if not action and params.get("text"):
        parsed = controller.parse_command(str(params.get("text", "")))
        action = parsed.get("action", "")
        target = parsed.get("target", "")
        value = parsed.get("value", "")
        metadata = parsed.get("metadata") or metadata

    if not action:
        return "Please specify a mobile action, sir."

    if action == "complete_pairing":
        code = str(params.get("pair_code", "")).strip()
        token = str(params.get("pair_token", "")).strip()
        result = controller.complete_pairing(code, token)
        return json.dumps(result)

    if action == "start_local_server":
        result = controller.start_local_server()
        return json.dumps(result)

    if action == "get_companion_page":
        return controller.get_companion_page()

    if action == "get_qr_payload":
        return json.dumps(controller.get_qr_payload())

    try:
        return controller.execute(action, target=target, value=value, metadata=metadata)
    except Exception as exc:
        return f"Mobile control failed: {exc}"


def main() -> None:
    controller = MobileController()
    info = controller.get_pairing_info()
    print(json.dumps(info, indent=2))
    print("\nMobile companion server is running. Press Ctrl+C to stop.")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("Stopping mobile companion server...")


if __name__ == "__main__":
    main()

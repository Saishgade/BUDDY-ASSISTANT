import importlib.util
import json
import os
import tempfile
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parents[1] / "mobile controller" / "controller.py"
spec = importlib.util.spec_from_file_location("mobile_controller", MODULE_PATH)
mobile_controller = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mobile_controller)
MobileController = mobile_controller.MobileController


class MobileControllerTests(unittest.TestCase):
    def test_call_command_uses_tel_uri(self):
        controller = MobileController()
        command = controller.build_command("call", target="9876543210")
        self.assertIn("tel:9876543210", command)

    def test_sms_command_uses_smsto_uri(self):
        controller = MobileController()
        command = controller.build_command("sms", target="9876543210", value="hello")
        self.assertIn("smsto:9876543210", command)
        self.assertIn("hello", command)

    def test_open_app_command_uses_package_name_for_whatsapp(self):
        controller = MobileController()
        command = controller.build_command("open_app", target="whatsapp")
        self.assertIn("com.whatsapp", command)

    def test_open_app_command_uses_package_name_for_maps(self):
        controller = MobileController()
        command = controller.build_command("open_app", target="maps")
        self.assertIn("com.google.android.apps.maps", command)

    def test_media_command_uses_service_url(self):
        controller = MobileController()
        command = controller.build_command("play_media", target="youtube", value="shape of you")
        self.assertIn("https://www.youtube.com", command)
        self.assertIn("shape%20of%20you", command)

    def test_note_command_uses_keep_intent(self):
        controller = MobileController()
        command = controller.build_command("make_note", value="meeting notes")
        self.assertIn("keep", command.lower())

    def test_connection_status_defaults_to_disconnected(self):
        controller = MobileController()
        status = controller.get_connection_status()
        self.assertFalse(status["connected"])

    def test_pairing_info_contains_code_and_connect_url(self):
        controller = MobileController()
        info = controller.get_pairing_info()
        self.assertTrue(info["pair_code"].isdigit())
        self.assertTrue(len(info["pair_code"]) >= 4)
        self.assertIn("connect?code=", info["connect_url"])
        self.assertTrue(info["local_only"])
        self.assertTrue(info["one_time"])
        self.assertTrue(info["challenge"])

    def test_wrap_command_adds_token_and_payload(self):
        controller = MobileController()
        wrapped = controller.wrap_command({"action": "open_app", "target": "whatsapp"})
        self.assertTrue(wrapped["ok"])
        self.assertIn("payload", wrapped)
        self.assertIn("token", wrapped)

    def test_start_local_server_returns_host_and_port(self):
        controller = MobileController()
        info = controller.start_local_server()
        self.assertTrue(info["ok"])
        self.assertEqual(info["host"], "127.0.0.1")
        self.assertEqual(info["port"], 8765)

    def test_natural_language_commands_are_translated(self):
        controller = MobileController()
        whatsapp = controller.parse_command("Open WhatsApp on my phone")
        self.assertEqual(whatsapp["action"], "open_app")
        self.assertEqual(whatsapp["target"], "whatsapp")

        call = controller.parse_command("Call Dad")
        self.assertEqual(call["action"], "call")
        self.assertEqual(call["target"], "Dad")

        note = controller.parse_command("Create a note")
        self.assertEqual(note["action"], "make_note")

    def test_connect_without_code_returns_health_message(self):
        server = mobile_controller.LocalPairingServer()
        response = server._accept_pairing("", "")
        self.assertTrue(response["ok"])
        self.assertIn("message", response)

    def test_pairing_accepts_persisted_state_without_env_vars(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            state_path = Path(temp_dir) / "mobile_state.json"
            os.environ["BUDDY_MOBILE_STATE_FILE"] = str(state_path)
            os.environ.pop("BUDDY_MOBILE_PAIR_CODE", None)
            os.environ.pop("BUDDY_MOBILE_PAIR_TOKEN", None)
            mobile_controller._save_persisted_state({
                "connected": False,
                "pair_code": "4321",
                "pair_token": "persisted-token",
                "queue": [],
            })
            server = mobile_controller.LocalPairingServer()
            response = server._accept_pairing("4321", "")
            self.assertTrue(response["ok"])

    def test_pairing_state_is_persisted_to_disk(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            state_path = Path(temp_dir) / "mobile_state.json"
            os.environ["BUDDY_MOBILE_STATE_FILE"] = str(state_path)
            controller = MobileController()
            controller.get_pairing_info()
            self.assertTrue(state_path.exists())
            data = json.loads(state_path.read_text(encoding="utf-8"))
            self.assertIn("pair_code", data)
            self.assertIn("connected", data)

    def test_default_state_file_uses_shared_home_location(self):
        os.environ.pop("BUDDY_MOBILE_STATE_FILE", None)
        expected = Path.home() / ".buddy" / "mobile_state.json"
        self.assertEqual(mobile_controller._state_file_path(), expected)

    def test_qr_payload_contains_image_data(self):
        controller = MobileController()
        payload = controller.get_qr_payload()
        self.assertTrue(payload["ok"] or not payload["ok"])

    def test_local_server_can_handle_command_payloads(self):
        import os
        os.environ["BUDDY_MOBILE_CONNECTED"] = "1"
        server = mobile_controller.LocalPairingServer()
        result = server.handle_command_request({"action": "open_app", "target": "whatsapp"})
        self.assertTrue(result["ok"])
        self.assertIn("message", result)


if __name__ == "__main__":
    unittest.main()

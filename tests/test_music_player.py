import unittest
from unittest.mock import patch

from music_player.player import MusicPlayer


class MusicPlayerTests(unittest.TestCase):
    def test_resolve_target_url_prefers_direct_result_when_available(self):
        player = MusicPlayer()
        player._lookup_first_result = lambda service, query: "https://www.youtube.com/watch?v=abc123"

        resolved = player._resolve_target_url("youtube", "test song")

        self.assertEqual(resolved, "https://www.youtube.com/watch?v=abc123")

    def test_play_uses_direct_url_when_resolved(self):
        player = MusicPlayer()
        player._resolve_target_url = lambda service, query: "https://www.youtube.com/watch?v=abc123"

        with patch.object(player, "_open_url") as mock_open:
            result = player.play("test song", "youtube")

        self.assertIn("https://www.youtube.com/watch?v=abc123", result)
        mock_open.assert_called_once_with("https://www.youtube.com/watch?v=abc123")


if __name__ == "__main__":
    unittest.main()

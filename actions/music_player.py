from __future__ import annotations

from music_player import music_player


def music_player_action(parameters=None, response=None, player=None):
    if player:
        player.write_log("SYS: Executing music player command.")

    params = parameters or {}
    query = str(params.get("query", "") or "").strip()
    service = str(params.get("service", "youtube") or "youtube").strip().lower()

    if not query:
        return "Please specify a song, artist, or playlist to play, sir."

    result = music_player.play(query=query, service=service)
    if player:
        player.write_log(f"SYS: Music target -> {result}")
    return result

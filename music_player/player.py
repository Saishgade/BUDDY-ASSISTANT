from yt_dlp import YoutubeDL
import webbrowser
import urllib.parse


class MusicPlayer:

    def __init__(self):
        pass

    def _lookup_first_result(self, query):
        try:
            with YoutubeDL({
                "quiet": True,
                "extract_flat": True,
                "skip_download": True
            }) as ydl:

                info = ydl.extract_info(
                    f"ytsearch1:{query}",
                    download=False
                )

                entries = info.get("entries", [])

                if not entries:
                    return None

                return entries[0]["id"]

        except Exception:
            return None

    def play(self, query, service="youtube"):

        service = service.lower()

        if service == "youtube":

            video = self._lookup_first_result(query)

            if not video:
                return "Song not found."

            url = f"https://www.youtube.com/watch?v={video}&autoplay=1"

            webbrowser.open(url)

            return f"Playing {query} on YouTube."

        elif service == "youtubemusic":

            video = self._lookup_first_result(query)

            if not video:
                return "Song not found."

            url = f"https://music.youtube.com/watch?v={video}"

            webbrowser.open(url)

            return f"Playing {query} on YouTube Music."

        elif service == "spotify":

            url = "https://open.spotify.com/search/" + urllib.parse.quote(query)

            webbrowser.open(url)

            return f"Searching {query} on Spotify."

        return "Unsupported service."


music_player = MusicPlayer()
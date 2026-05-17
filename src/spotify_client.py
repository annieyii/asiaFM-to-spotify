"""Spotify API wrapper — search tracks and build playlists."""

import os
import spotipy
from spotipy.oauth2 import SpotifyOAuth


SCOPE = "playlist-modify-public playlist-modify-private"


def get_client() -> spotipy.Spotify:
    """
    Returns an authenticated Spotify client.
    Reads SPOTIPY_CLIENT_ID, SPOTIPY_CLIENT_SECRET, SPOTIPY_REDIRECT_URI from env.
    On first run, opens a browser for OAuth login.
    """
    auth_manager = SpotifyOAuth(
        client_id=os.environ["SPOTIPY_CLIENT_ID"],
        client_secret=os.environ["SPOTIPY_CLIENT_SECRET"],
        redirect_uri=os.environ["SPOTIPY_REDIRECT_URI"],
        scope=SCOPE,
        open_browser=True,
        cache_path=".spotify_cache",
    )
    return spotipy.Spotify(auth_manager=auth_manager)


def search_track(sp: spotipy.Spotify, title: str, artist: str) -> str | None:
    """Return Spotify track URI for the best match, or None if not found."""
    query = f"track:{title} artist:{artist}"
    result = sp.search(q=query, type="track", limit=1, market="TW")
    items = result["tracks"]["items"]
    if items:
        return items[0]["uri"]
    # Fallback: looser search without field specifiers
    result = sp.search(q=f"{title} {artist}", type="track", limit=1, market="TW")
    items = result["tracks"]["items"]
    if items:
        return items[0]["uri"]
    return None


def parse_playlist_id(id_or_url: str) -> str:
    """Accept a playlist ID or full Spotify URL/URI."""
    id_or_url = id_or_url.strip()
    if "spotify.com/playlist/" in id_or_url:
        return id_or_url.split("spotify.com/playlist/")[1].split("?")[0]
    if id_or_url.startswith("spotify:playlist:"):
        return id_or_url.split(":")[-1]
    return id_or_url


def _search_and_add(sp: spotipy.Spotify, playlist_id: str, songs: list[dict]) -> str:
    uris: list[str] = []
    not_found: list[dict] = []

    print(f"\n在 Spotify 搜尋 {len(songs)} 首歌曲...")
    for i, song in enumerate(songs, 1):
        uri = search_track(sp, song["title"], song["artist"])
        if uri:
            uris.append(uri)
        else:
            not_found.append(song)
        if i % 10 == 0:
            print(f"  {i}/{len(songs)} ...", flush=True)

    for i in range(0, len(uris), 100):
        sp.playlist_add_items(playlist_id, uris[i:i + 100])

    print(f"\n成功加入: {len(uris)} 首")
    if not_found:
        print(f"找不到 ({len(not_found)} 首):")
        for s in not_found:
            print(f"  - {s['title']} — {s['artist']}")

    playlist = sp.playlist(playlist_id, fields="external_urls")
    return playlist["external_urls"]["spotify"]


def create_playlist(
    sp: spotipy.Spotify,
    name: str,
    songs: list[dict],
    public: bool = True,
) -> str:
    """Create a new Spotify playlist and add all found tracks."""
    playlist = sp._post("me/playlists", payload={"name": name, "public": public})
    return _search_and_add(sp, playlist["id"], songs)


def add_to_playlist(
    sp: spotipy.Spotify,
    playlist_id_or_url: str,
    songs: list[dict],
) -> str:
    """Add tracks to an existing playlist. Accepts ID, URL, or URI."""
    playlist_id = parse_playlist_id(playlist_id_or_url)
    return _search_and_add(sp, playlist_id, songs)

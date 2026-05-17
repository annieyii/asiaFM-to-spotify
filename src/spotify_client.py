"""Spotify API wrapper — search tracks and build playlists."""

import json
import os
import time
from pathlib import Path

import spotipy
from spotipy.oauth2 import SpotifyOAuth

SCOPE = "playlist-modify-public playlist-modify-private"
CACHE_FILE = Path(".song_cache.json")


def get_client() -> spotipy.Spotify:
    auth_manager = SpotifyOAuth(
        client_id=os.environ["SPOTIPY_CLIENT_ID"],
        client_secret=os.environ["SPOTIPY_CLIENT_SECRET"],
        redirect_uri=os.environ["SPOTIPY_REDIRECT_URI"],
        scope=SCOPE,
        open_browser=True,
        cache_path=".spotify_cache",
    )
    return spotipy.Spotify(auth_manager=auth_manager)


def _load_cache() -> dict:
    if CACHE_FILE.exists():
        return json.loads(CACHE_FILE.read_text(encoding="utf-8"))
    return {}


def _save_cache(cache: dict) -> None:
    CACHE_FILE.write_text(json.dumps(cache, ensure_ascii=False, indent=2), encoding="utf-8")


def search_track(sp: spotipy.Spotify, title: str, artist: str, cache: dict) -> str | None:
    key = f"{title}|{artist}"
    if key in cache:
        return cache[key]  # None means previously confirmed not found

    for attempt in range(3):
        try:
            result = sp.search(q=f"track:{title} artist:{artist}", type="track", limit=1, market="TW")
            items = result["tracks"]["items"]
            if items:
                uri = items[0]["uri"]
                cache[key] = uri
                return uri

            result = sp.search(q=f"{title} {artist}", type="track", limit=1, market="TW")
            items = result["tracks"]["items"]
            uri = items[0]["uri"] if items else None
            cache[key] = uri
            return uri

        except spotipy.SpotifyException as e:
            if e.http_status == 429:
                wait = int(e.headers.get("Retry-After", 5)) if e.headers else 5
                print(f"\n  rate limit，等待 {wait} 秒...", flush=True)
                time.sleep(wait + 1)
            else:
                raise

    return None


def parse_playlist_id(id_or_url: str) -> str:
    id_or_url = id_or_url.strip()
    if "spotify.com/playlist/" in id_or_url:
        return id_or_url.split("spotify.com/playlist/")[1].split("?")[0]
    if id_or_url.startswith("spotify:playlist:"):
        return id_or_url.split(":")[-1]
    return id_or_url


def _search_and_add(sp: spotipy.Spotify, playlist_id: str, songs: list[dict]) -> str:
    cache = _load_cache()
    cached_count = sum(1 for s in songs if f"{s['title']}|{s['artist']}" in cache)
    need_search = len(songs) - cached_count

    print(f"\n在 Spotify 搜尋 {len(songs)} 首歌曲（快取命中 {cached_count} 首，需搜尋 {need_search} 首）...")

    uris: list[str] = []
    not_found: list[dict] = []

    for i, song in enumerate(songs, 1):
        uri = search_track(sp, song["title"], song["artist"], cache)
        if uri:
            uris.append(uri)
        else:
            not_found.append(song)
        if i % 20 == 0:
            print(f"  {i}/{len(songs)} ...", flush=True)
            _save_cache(cache)  # 定期存檔，避免中途中斷損失進度

    _save_cache(cache)

    for i in range(0, len(uris), 100):
        sp.playlist_add_items(playlist_id, uris[i:i + 100])

    print(f"\n成功加入: {len(uris)} 首")
    if not_found:
        print(f"找不到 ({len(not_found)} 首):")
        for s in not_found:
            print(f"  - {s['title']} — {s['artist']}")

    playlist = sp.playlist(playlist_id, fields="external_urls")
    return playlist["external_urls"]["spotify"]


def create_playlist(sp: spotipy.Spotify, name: str, songs: list[dict], public: bool = True) -> str:
    playlist = sp._post("me/playlists", payload={"name": name, "public": public})
    return _search_and_add(sp, playlist["id"], songs)


def add_to_playlist(sp: spotipy.Spotify, playlist_id_or_url: str, songs: list[dict]) -> str:
    return _search_and_add(sp, parse_playlist_id(playlist_id_or_url), songs)

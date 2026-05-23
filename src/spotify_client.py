"""Spotify API wrapper — search tracks and build playlists."""

import csv
import json
import os
import time
from datetime import datetime
from pathlib import Path

import spotipy
from spotipy.oauth2 import SpotifyOAuth

SCOPE = "playlist-modify-public playlist-modify-private"
CACHE_FILE = Path(".song_cache.json")
NOT_FOUND_FILE = Path("not_found_songs.csv")


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


def _save_not_found(songs: list[dict]) -> None:
    write_header = not NOT_FOUND_FILE.exists()
    with NOT_FOUND_FILE.open("a", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=["searched_at", "title", "artist"])
        if write_header:
            writer.writeheader()
        now = datetime.now().strftime("%Y-%m-%d %H:%M")
        writer.writerows({"searched_at": now, **s} for s in songs)
    print(f"已記錄到 {NOT_FOUND_FILE}")


def search_track(sp: spotipy.Spotify, title: str, artist: str, cache: dict, log: callable = print) -> str | None:
    key = f"{title}|{artist}"
    if key in cache:
        return cache[key]  # None means previously confirmed not found

    for retry in range(3):
        try:
            result = sp.search(q=f"track:{title} artist:{artist}", type="track", limit=1, market="TW")
            items = result["tracks"]["items"]
            if items:
                uri = items[0]["uri"]
                cache[key] = uri
                time.sleep(0.1)
                return uri

            time.sleep(0.1)
            result = sp.search(q=f"{title} {artist}", type="track", limit=1, market="TW")
            items = result["tracks"]["items"]
            uri = items[0]["uri"] if items else None
            cache[key] = uri
            time.sleep(0.1)
            return uri

        except spotipy.SpotifyException as e:
            if e.http_status == 429:
                # Retry-After 優先，否則指數退避 (1s, 2s, 4s)
                wait = int(e.headers.get("Retry-After", 2 ** retry)) if e.headers else 2 ** retry
                log(f"  rate limit，等待 {wait} 秒... (第 {retry + 1} 次重試)")
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


def _search_and_add(
    sp: spotipy.Spotify,
    playlist_id: str,
    songs: list[dict],
    on_batch_added: callable = None,
    log: callable = print,
) -> str:
    cache = _load_cache()
    cached_count = sum(1 for s in songs if f"{s['title']}|{s['artist']}" in cache)
    need_search = len(songs) - cached_count

    log(f"在 Spotify 搜尋 {len(songs)} 首歌曲（快取命中 {cached_count} 首，需搜尋 {need_search} 首）...")

    uris_batch: list[str] = []
    total_added = 0
    not_found: list[dict] = []

    for i, song in enumerate(songs, 1):
        uri = search_track(sp, song["title"], song["artist"], cache, log=log)
        if uri:
            uris_batch.append(uri)
        else:
            not_found.append(song)

        if len(uris_batch) >= 100:
            sp.playlist_add_items(playlist_id, uris_batch)
            total_added += len(uris_batch)
            uris_batch = []
            if on_batch_added:
                on_batch_added(i)

        if i % 20 == 0:
            log(f"  {i}/{len(songs)} ...")
            _save_cache(cache)

    if uris_batch:
        sp.playlist_add_items(playlist_id, uris_batch)
        total_added += len(uris_batch)
        if on_batch_added:
            on_batch_added(len(songs))

    _save_cache(cache)

    log(f"成功加入: {total_added} 首")
    if not_found:
        log(f"找不到 ({len(not_found)} 首):")
        for s in not_found:
            log(f"  - {s['title']} — {s['artist']}")
        _save_not_found(not_found)

    playlist = sp.playlist(playlist_id, fields="external_urls")
    return playlist["external_urls"]["spotify"]


def create_playlist(
    sp: spotipy.Spotify, name: str, songs: list[dict], public: bool = True, on_batch_added: callable = None, log: callable = print
) -> str:
    playlist = sp._post("me/playlists", payload={"name": name, "public": public})
    return _search_and_add(sp, playlist["id"], songs, on_batch_added=on_batch_added, log=log)


def add_to_playlist(
    sp: spotipy.Spotify, playlist_id_or_url: str, songs: list[dict], on_batch_added: callable = None, log: callable = print
) -> str:
    return _search_and_add(sp, parse_playlist_id(playlist_id_or_url), songs, on_batch_added=on_batch_added, log=log)

"""
Asia FM → Spotify

不帶參數執行會進入互動問答模式。
也可以直接用 flag 跳過問答：

  uv run main.py --start 2026-05-10 --end 2026-05-17
  uv run main.py --start 2026-05-17 --stations asia
  uv run main.py --start 2026-05-17 --export songs.csv   # 只輸出 CSV
"""

import argparse
import csv
import os
import sys
from datetime import date, datetime, timedelta

from dotenv import load_dotenv

from src.scraper import scrape

load_dotenv()

TODAY = date.today()


def parse_date(s: str) -> date:
    return datetime.strptime(s, "%Y-%m-%d").date()


def ask(prompt: str, default: str = "") -> str:
    hint = f" [{default}]" if default else ""
    try:
        val = input(f"{prompt}{hint}: ").strip()
    except (EOFError, KeyboardInterrupt):
        print()
        sys.exit(0)
    return val or default


def ask_stations() -> list[str]:
    print("\n電台選擇:")
    print("  1) 亞洲電台 FM92.7")
    print("  2) 亞太電台 FM92.3")
    print("  3) 兩個都要")
    choice = ask("請選擇", "3")
    if choice == "1":
        return ["asia"]
    if choice == "2":
        return ["pacific"]
    return ["asia", "pacific"]


def ask_dates() -> tuple[date, date]:
    default_start = (TODAY - timedelta(days=6)).strftime("%Y-%m-%d")
    default_end = TODAY.strftime("%Y-%m-%d")

    print("\n日期範圍:")
    while True:
        try:
            start = parse_date(ask("開始日期 (YYYY-MM-DD)", default_start))
            break
        except ValueError:
            print("  格式錯誤，請重新輸入")
    while True:
        try:
            end = parse_date(ask("結束日期 (YYYY-MM-DD)", default_end))
            if end >= start:
                break
            print("  結束日期不能早於開始日期")
        except ValueError:
            print("  格式錯誤，請重新輸入")
    return start, end


def ask_output(stations: list[str], start: date, end: date) -> dict:
    print("\n輸出方式:")
    print("  1) 加入現有 Spotify 歌單")
    print("  2) 建立新 Spotify 歌單")
    print("  3) 匯出 CSV 檔案")
    choice = ask("請選擇", "1")

    if choice == "3":
        path = ask("CSV 檔案名稱", "songs.csv")
        return {"mode": "csv", "path": path}

    if choice == "1":
        saved = os.environ.get("SPOTIFY_PLAYLIST_ID", "")
        playlist_id = ask("歌單網址或 ID", saved)
        return {"mode": "add", "playlist_id": playlist_id}

    station_label = "+".join(stations)
    default_name = f"Asia FM ({station_label}) {start}~{end}"
    name = ask("歌單名稱", default_name)
    return {"mode": "spotify", "name": name, "public": False}


def export_csv(songs: list[dict], path: str) -> None:
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=["title", "artist"])
        writer.writeheader()
        writer.writerows(songs)
    print(f"已匯出 CSV: {path}")


def get_spotify_client():
    missing = [v for v in ("SPOTIPY_CLIENT_ID", "SPOTIPY_CLIENT_SECRET") if not os.environ.get(v)]
    if missing:
        print("\n缺少 Spotify 憑證:", ", ".join(missing))
        print("請複製 .env.example 為 .env 並填入你的 Spotify App 設定。")
        sys.exit(1)
    from src.spotify_client import get_client
    return get_client()


def run_spotify_new(songs: list[dict], name: str, public: bool) -> None:
    from src.spotify_client import create_playlist
    print(f"\n連線 Spotify，建立歌單:「{name}」")
    url = create_playlist(get_spotify_client(), name, songs, public=public)
    print(f"\n歌單已建立: {url}")


def run_spotify_add(songs: list[dict], playlist_id: str) -> None:
    from src.spotify_client import add_to_playlist
    print("\n連線 Spotify，加入歌單...")
    url = add_to_playlist(get_spotify_client(), playlist_id, songs)
    print(f"\n完成: {url}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Asia FM → Spotify playlist builder",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--start", type=parse_date, default=None, help="開始日期 YYYY-MM-DD")
    parser.add_argument("--end", type=parse_date, default=None, help="結束日期 YYYY-MM-DD")
    parser.add_argument("--stations", nargs="+", choices=["asia", "pacific"], default=None)
    parser.add_argument("--export", metavar="FILE.csv", help="只匯出 CSV")
    parser.add_argument("--playlist-id", default=None, help="加入現有歌單（ID 或網址）")
    parser.add_argument("--playlist-name", default=None, help="建立新歌單時的名稱")
    parser.add_argument("--private", action="store_true", help="建立私人歌單（預設即私人）")
    args = parser.parse_args()

    # Interactive mode when --start is omitted
    if args.start is None:
        print("=== Asia FM → Spotify ===")
        stations = ask_stations()
        start, end = ask_dates()
        output = ask_output(stations, start, end)
    else:
        stations = args.stations or ["asia", "pacific"]
        start = args.start
        end = args.end or args.start
        if args.export:
            output = {"mode": "csv", "path": args.export}
        elif args.playlist_id:
            output = {"mode": "add", "playlist_id": args.playlist_id}
        else:
            station_label = "+".join(stations)
            output = {
                "mode": "spotify",
                "name": args.playlist_name or f"Asia FM ({station_label}) {start}~{end}",
                "public": not args.private,
            }

    print()
    songs = scrape(stations, start, end)

    if not songs:
        print("沒有抓到任何歌曲，結束。")
        sys.exit(0)

    if output["mode"] == "csv":
        export_csv(songs, output["path"])
    elif output["mode"] == "add":
        run_spotify_add(songs, output["playlist_id"])
    else:
        run_spotify_new(songs, output["name"], output["public"])


if __name__ == "__main__":
    main()

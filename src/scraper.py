"""Asia FM song scraper — hits the WordPress AJAX endpoint directly."""

import time
from datetime import date, timedelta
from typing import Iterator

import requests

AJAX_URL = "https://www.asiafm.com.tw/wp-admin/admin-ajax.php"

STATIONS = {
    "asia": "94",    # 亞洲電台 FM92.7
    "pacific": "97", # 亞太電台 FM92.3
}

TIME_SLOTS = [
    "00:00:00-02:00:00",
    "02:00:00-04:00:00",
    "04:00:00-06:00:00",
    "06:00:00-08:00:00",
    "08:00:00-10:00:00",
    "10:00:00-12:00:00",
    "12:00:00-14:00:00",
    "14:00:00-16:00:00",
    "16:00:00-18:00:00",
    "18:00:00-20:00:00",
    "20:00:00-22:00:00",
    "22:00:00-00:00:00",
]


def date_range(start: date, end: date) -> Iterator[date]:
    d = start
    while d <= end:
        yield d
        d += timedelta(days=1)


def fetch_slot(radio_type: str, search_date: str, interval: str) -> list[dict]:
    try:
        resp = requests.post(
            AJAX_URL,
            data={
                "action": "search_songs",
                "radioType": radio_type,
                "searchDate": search_date,
                "searchInterval": interval,
            },
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()
        if data.get("status") == 1:
            return data["html"]
    except Exception as e:
        print(f"  警告: 無法取得 {search_date} {interval} — {e}")
    return []


def scrape(
    stations: list[str],
    start: date,
    end: date,
    delay: float = 0.3,
) -> list[dict]:
    """
    Scrape songs for given station keys ('asia', 'pacific') and date range.
    Returns deduplicated list of {title, artist} dicts.
    """
    seen: set[tuple[str, str]] = set()
    songs: list[dict] = []

    for station_key in stations:
        radio_type = STATIONS[station_key]
        station_name = "亞洲FM92.7" if station_key == "asia" else "亞太FM92.3"
        print(f"\n[{station_name}]")

        for d in date_range(start, end):
            date_str = d.strftime("%Y-%m-%d")
            print(f"  {date_str} ...", end=" ", flush=True)
            count = 0
            for slot in TIME_SLOTS:
                for song in fetch_slot(radio_type, date_str, slot):
                    key = (song["title"].strip(), song["artist"].strip())
                    if key not in seen:
                        seen.add(key)
                        songs.append({"title": key[0], "artist": key[1]})
                        count += 1
                time.sleep(delay)
            print(f"+{count} 首")

    print(f"\n共抓取 {len(songs)} 首不重複歌曲")
    return songs

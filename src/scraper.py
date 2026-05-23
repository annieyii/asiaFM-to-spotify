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


def fetch_slot(radio_type: str, search_date: str, interval: str, log: callable = print) -> list[dict]:
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
        msg = data.get("message") or data.get("msg") or f"status={data.get('status')}"
        log(f"  警告: {search_date} {interval} — {msg}")
    except Exception as e:
        log(f"  警告: 無法取得 {search_date} {interval} — {e}")
    return []


def _filter_slots(time_start: str | None, time_end: str | None) -> list[str]:
    """Return only slots that overlap with [time_start, time_end] (HH:MM format)."""
    if not time_start and not time_end:
        return TIME_SLOTS

    def to_hour(t: str) -> int:
        return int(t.split(":")[0])

    h_start = to_hour(time_start) if time_start else 0
    h_end = to_hour(time_end) if time_end else 24

    result = []
    for slot in TIME_SLOTS:
        s, e = slot.split("-")
        slot_start = to_hour(s)
        slot_end = to_hour(e) if to_hour(e) != 0 else 24
        if slot_start < h_end and slot_end > h_start:
            result.append(slot)
    return result


def scrape(
    stations: list[str],
    start: date,
    end: date,
    time_start: str | None = None,
    time_end: str | None = None,
    delay: float = 0.3,
    log: callable = print,
) -> list[dict]:
    """
    Scrape songs for given station keys ('asia', 'pacific') and date range.
    time_start / time_end: optional HH:MM strings to limit time of day.
    Returns deduplicated list of {title, artist} dicts.
    """
    slots = _filter_slots(time_start, time_end)
    time_label = f" {time_start}~{time_end}" if time_start or time_end else ""

    seen: set[tuple[str, str]] = set()
    songs: list[dict] = []

    for station_key in stations:
        radio_type = STATIONS[station_key]
        station_name = "亞洲FM92.7" if station_key == "asia" else "亞太FM92.3"
        log(f"[{station_name}{time_label}]")

        for d in date_range(start, end):
            date_str = d.strftime("%Y-%m-%d")
            count = 0
            for slot in slots:
                for song in fetch_slot(radio_type, date_str, slot, log=log):
                    key = (song["title"].strip(), song["artist"].strip())
                    if key not in seen:
                        seen.add(key)
                        songs.append({"title": key[0], "artist": key[1]})
                        count += 1
                time.sleep(delay)
            log(f"  {date_str}: +{count} 首")

    log(f"共抓取 {len(songs)} 首不重複歌曲")
    return songs

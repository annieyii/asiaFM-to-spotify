"""Asia FM → Spotify — Streamlit web UI"""

import csv
import io
import json
import os
from datetime import date
from pathlib import Path

import streamlit as st
from dotenv import load_dotenv

load_dotenv()

TODAY = date.today()
CONFIG_FILE = Path(".spotify_config.json")
PENDING_FILE = Path(".pending_songs.json")


def load_default_playlist() -> str:
    if not CONFIG_FILE.exists():
        return os.environ.get("SPOTIFY_PLAYLIST_ID", "")
    return json.loads(CONFIG_FILE.read_text(encoding="utf-8")).get("default_playlist_id", "")


def save_default_playlist(url: str) -> None:
    CONFIG_FILE.write_text(
        json.dumps({"default_playlist_id": url}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def load_pending() -> tuple[list[dict], dict] | None:
    if not PENDING_FILE.exists():
        return None
    data = json.loads(PENDING_FILE.read_text(encoding="utf-8"))
    return data["songs"], data["output"]


def save_pending(songs: list[dict], output: dict) -> None:
    PENDING_FILE.write_text(
        json.dumps({"songs": songs, "output": output}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def clear_pending() -> None:
    PENDING_FILE.unlink(missing_ok=True)


# ── 頁面設定 ──────────────────────────────────────────────────
st.set_page_config(page_title="Asia FM → Spotify", page_icon="🎵", layout="centered")
st.title("🎵 Asia FM → Spotify")

missing_creds = [v for v in ("SPOTIPY_CLIENT_ID", "SPOTIPY_CLIENT_SECRET") if not os.environ.get(v)]
if missing_creds:
    st.error(f"缺少 Spotify 憑證：{', '.join(missing_creds)}。請確認 .env 已設定。")
    st.stop()

# ── Session state 初始化 ──────────────────────────────────────
if "songs" not in st.session_state:
    st.session_state.songs = None
if "scrape_warnings" not in st.session_state:
    st.session_state.scrape_warnings = []


# ── 未完成任務提示 ────────────────────────────────────────────
pending = load_pending()
if pending and st.session_state.songs is None:
    pending_songs, pending_output = pending
    mode_label = {
        "add": f"加入歌單 {pending_output.get('playlist_id', '')}",
        "spotify": f"建立歌單「{pending_output.get('name', '')}」",
    }.get(pending_output.get("mode", ""), pending_output.get("mode", ""))

    st.info(f"找到上次未完成的 {len(pending_songs)} 首歌（{mode_label}）")
    col1, col2 = st.columns(2)
    if col1.button("繼續上次", use_container_width=True, type="primary"):
        st.session_state.songs = pending_songs
        st.session_state.pending_output = pending_output
        st.rerun()
    if col2.button("丟棄，重新開始", use_container_width=True):
        clear_pending()
        st.rerun()

# ── 步驟一：抓取設定 ─────────────────────────────────────────
st.subheader("電台")
col1, col2 = st.columns(2)
asia = col1.checkbox("亞洲電台 FM92.7", value=True)
pacific = col2.checkbox("亞太電台 FM92.3", value=True)

st.subheader("日期範圍")
col1, col2 = st.columns(2)
start_date = col1.date_input("開始日期", TODAY)
end_date = col2.date_input("結束日期", TODAY)

with st.expander("時間範圍（選填，留空代表全天）"):
    col1, col2 = st.columns(2)
    time_start = col1.text_input("開始時間 HH:MM", "")
    time_end = col2.text_input("結束時間 HH:MM", "")

if st.button("開始抓取", type="primary", use_container_width=True):
    stations = (["asia"] if asia else []) + (["pacific"] if pacific else [])
    if not stations:
        st.error("請至少選擇一個電台")
        st.stop()
    if end_date < start_date:
        st.error("結束日期不能早於開始日期")
        st.stop()

    from src.scraper import scrape

    collected_warnings = []

    def scrape_log(msg):
        st.write(msg)
        if "警告" in str(msg):
            collected_warnings.append(msg)

    with st.status("抓取歌單中...", expanded=True) as status:
        songs = scrape(
            stations,
            start_date,
            end_date,
            time_start=time_start or None,
            time_end=time_end or None,
            log=scrape_log,
        )
        if songs:
            status.update(label=f"抓取完成，共 {len(songs)} 首歌", state="complete")
            st.session_state.songs = songs
            st.session_state.pop("pending_output", None)
        else:
            status.update(label="沒有抓到任何歌曲", state="error")

    st.session_state.scrape_warnings = collected_warnings

for w in st.session_state.scrape_warnings:
    st.warning(w)

# ── 步驟二：輸出（抓完後才顯示）─────────────────────────────
if st.session_state.songs:
    songs = st.session_state.songs
    # 若從 pending 恢復，預設輸出方式跟上次一樣
    pending_output = st.session_state.get("pending_output")

    st.divider()

    with st.expander(f"歌曲列表（{len(songs)} 首）"):
        for s in songs:
            st.write(f"- {s['title']} — {s['artist']}")

    st.subheader("輸出方式")
    default_playlist = load_default_playlist()

    default_mode_index = 0 if default_playlist else 1
    if pending_output:
        mode_map = {"add": 0, "spotify": 1, "csv": 2}
        default_mode_index = mode_map.get(pending_output.get("mode", ""), default_mode_index)

    output_mode = st.radio(
        "輸出方式",
        ["加入現有歌單", "建立新歌單", "匯出 CSV"],
        index=default_mode_index,
        label_visibility="collapsed",
    )

    def run_spotify(sp, output: dict):
        from src.spotify_client import add_to_playlist, create_playlist

        def on_batch_added(processed_count: int):
            remaining = songs[processed_count:]
            if remaining:
                save_pending(remaining, output)
            else:
                clear_pending()

        save_pending(songs, output)
        if output["mode"] == "add":
            return add_to_playlist(sp, output["playlist_id"], songs, on_batch_added=on_batch_added, log=st.write)
        else:
            url = create_playlist(sp, output["name"], songs, public=False, on_batch_added=on_batch_added, log=st.write)
            save_default_playlist(url)
            return url

    if output_mode == "加入現有歌單":
        default_id = pending_output.get("playlist_id", default_playlist) if pending_output else default_playlist
        playlist_id = st.text_input("歌單網址或 ID", default_id)
        if st.button("加入歌單", type="primary", use_container_width=True):
            from src.spotify_client import get_client
            output = {"mode": "add", "playlist_id": playlist_id}
            with st.status("連線 Spotify...", expanded=True) as status:
                sp = get_client()
                url = run_spotify(sp, output)
                clear_pending()
                status.update(label="完成！", state="complete")
            st.success("歌單已更新")
            st.link_button("開啟 Spotify 歌單 🎵", url, use_container_width=True)

    elif output_mode == "建立新歌單":
        default_name = pending_output.get("name", f"Asia FM {TODAY}") if pending_output else f"Asia FM {TODAY}"
        playlist_name = st.text_input("歌單名稱", default_name)
        if st.button("建立歌單", type="primary", use_container_width=True):
            from src.spotify_client import get_client
            output = {"mode": "spotify", "name": playlist_name, "public": False}
            with st.status("連線 Spotify...", expanded=True) as status:
                sp = get_client()
                url = run_spotify(sp, output)
                clear_pending()
                status.update(label="完成！", state="complete")
            st.success("歌單已建立")
            st.link_button("開啟 Spotify 歌單 🎵", url, use_container_width=True)

    else:
        csv_filename = st.text_input("CSV 檔案名稱", "songs.csv")
        buf = io.StringIO()
        writer = csv.DictWriter(buf, fieldnames=["title", "artist"])
        writer.writeheader()
        writer.writerows(songs)
        st.download_button(
            "下載 CSV",
            buf.getvalue(),
            file_name=csv_filename or "songs.csv",
            mime="text/csv",
            use_container_width=True,
        )

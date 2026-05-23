# Asia FM → Spotify

從[亞洲電台](https://www.asiafm.com.tw/)抓取播放歌曲，自動加入 Spotify 歌單。

支援亞洲電台 FM92.7 與亞太電台 FM92.3，可指定任意日期與時間範圍。

## 安裝

需要 [uv](https://docs.astral.sh/uv/getting-started/installation/)。

```bash
git clone https://github.com/your-username/asiaFM-to-spotify.git
cd asiaFM-to-spotify
uv sync
```

## 設定 Spotify

1. 前往 [Spotify Developer Dashboard](https://developer.spotify.com/dashboard) 建立免費 App
   - Redirect URI：必填
   - APIs 勾選：**Web API**
   - 在 App Settings → User Management 加入你的 Spotify 帳號 email

2. 複製並填入憑證：

```bash
cp .env.example .env
```

```env
SPOTIPY_CLIENT_ID=你的 Client ID
SPOTIPY_CLIENT_SECRET=你的 Client Secret
SPOTIPY_REDIRECT_URI=http://...

# 固定歌單（貼上 Spotify 歌單網址，不填則每次新建）
SPOTIFY_PLAYLIST_ID=https://open.spotify.com/playlist/...
```

## 使用

### Web UI

```bash
uv run streamlit run app.py
```

瀏覽器開啟後，選擇電台、日期、輸出方式，按「開始抓取」即可。

### Terminal 互動模式

```bash
uv run main.py
```

依提示選擇電台、日期、時間範圍、輸出方式，直接按 Enter 套用預設值。

```
=== Asia FM → Spotify ===

電台選擇:
  1) 亞洲電台 FM92.7
  2) 亞太電台 FM92.3
  3) 兩個都要
請選擇 [3]:

日期範圍:
開始日期 (YYYY-MM-DD) [2026-05-22]:
結束日期 (YYYY-MM-DD) [2026-05-22]:

時間範圍（直接 Enter 代表全天）:
開始時間 HH:MM:
結束時間 HH:MM:

輸出方式:
  1) 加入現有 Spotify 歌單
  2) 建立新 Spotify 歌單
  3) 匯出 CSV 檔案
請選擇 [1]:
```

### 指令模式

```bash
# 加入現有歌單
uv run main.py --start 2026-05-10 --end 2026-05-17 --playlist-id https://open.spotify.com/playlist/xxx

# 只抓早上時段，建立新歌單
uv run main.py --start 2026-05-17 --time-start 06:00 --time-end 12:00

# 只匯出 CSV（不需要 Spotify 帳號）
uv run main.py --start 2026-05-17 --export songs.csv
```

| Flag | 說明 |
|------|------|
| `--start` | 開始日期 `YYYY-MM-DD` |
| `--end` | 結束日期（預設同 `--start`） |
| `--stations` | `asia` / `pacific` / 兩個都不填代表全選 |
| `--time-start` | 只抓此時間之後的時段（格式 `HH:MM`） |
| `--time-end` | 只抓此時間之前的時段（格式 `HH:MM`） |
| `--playlist-id` | 加入現有歌單（ID 或完整網址） |
| `--playlist-name` | 建立新歌單時的名稱 |
| `--export` | 只輸出 CSV，不操作 Spotify |

### 中途中斷與續跑

抓完電台歌單後，程式會先把歌曲存到本地 `.pending_songs.json`，再開始 Spotify 搜尋。若中途遇到 rate limit 或手動中斷，下次執行時會自動詢問是否繼續：

```
找到上次未完成的 480 首歌。
要繼續加入 Spotify 歌單嗎？(y/n) [y]:
```

搜尋結果也會快取在 `.song_cache.json`，重複出現的歌不會重複呼叫 API。

## 檔案結構

```
asiaFM-to-spotify/
├── main.py                  # CLI 入口，互動問答與 flag 處理
├── app.py                   # Streamlit web UI
├── src/
│   ├── scraper.py           # 向亞洲電台 AJAX endpoint 抓取歌單
│   └── spotify_client.py    # Spotify OAuth、搜尋、建立/加入歌單
├── .env                     # 你的憑證（不進版控）
└── .env.example             # 憑證範本
```

## 運作原理

1. 直接呼叫亞洲電台網站的 WordPress AJAX endpoint 抓取每個時段的播放清單
2. 對每首歌在 Spotify 搜尋（先用精確搜尋，找不到再用模糊搜尋），結果快取在本地
3. 以每批 100 首的方式加入歌單（Spotify API 上限）

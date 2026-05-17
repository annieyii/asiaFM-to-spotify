# Asia FM → Spotify

從[亞洲電台](https://www.asiafm.com.tw/)抓取播放歌曲，自動加入 Spotify 歌單。

支援亞洲電台 FM92.7 與亞太電台 FM92.3，可指定任意日期範圍。

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

### 互動模式（推薦）

```bash
uv run main.py
```

依提示選擇電台、日期、輸出方式，直接按 Enter 套用預設值。

```
=== Asia FM → Spotify ===

電台選擇:
  1) 亞洲電台 FM92.7
  2) 亞太電台 FM92.3
  3) 兩個都要
請選擇 [3]:

日期範圍:
開始日期 (YYYY-MM-DD) [2026-05-11]:
結束日期 (YYYY-MM-DD) [2026-05-17]:

輸出方式:
  1) 加入現有 Spotify 歌單
  2) 建立新 Spotify 歌單（私人）
  3) 匯出 CSV 檔案
請選擇 [1]:
```

### 指令模式

```bash
# 加入現有歌單
uv run main.py --start 2026-05-10 --end 2026-05-17 --playlist-id https://open.spotify.com/playlist/xxx

# 建立新私人歌單
uv run main.py --start 2026-05-17 --stations asia

# 只匯出 CSV（不需要 Spotify 帳號）
uv run main.py --start 2026-05-17 --export songs.csv
```

| Flag | 說明 |
|------|------|
| `--start` | 開始日期 `YYYY-MM-DD` |
| `--end` | 結束日期（預設同 `--start`） |
| `--stations` | `asia` / `pacific` / 兩個都不填代表全選 |
| `--playlist-id` | 加入現有歌單（ID 或完整網址） |
| `--playlist-name` | 建立新歌單時的名稱 |
| `--export` | 只輸出 CSV，不操作 Spotify |

## 檔案結構

```
asiaFM-to-spotify/
├── main.py                  # 入口，互動問答與 CLI flag 處理
├── src/
│   ├── scraper.py           # 向亞洲電台 AJAX endpoint 抓取歌單
│   └── spotify_client.py    # Spotify OAuth、搜尋、建立/加入歌單
├── .env                     # 你的憑證
└── .env.example             # 憑證範本
```

## 運作原理

1. 直接呼叫亞洲電台網站的 WordPress AJAX endpoint 抓取每個時段的播放清單
2. 對每首歌在 Spotify 搜尋（先用精確搜尋，找不到再用模糊搜尋）
3. 以每批 100 首的方式加入歌單（Spotify API 上限）

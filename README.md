# CRITShowCase

CRITShowCase（B50 影片）的出片工具。讀 [critlog.me](https://critlog.me) 的 CRITShowCase 頁面匯出的影片專案（zip），在你自己的電腦上下載需要的 YouTube 片段，合成一支 mp4。

每個段落的畫面（曲名、成績、評論、非官方標示）都由網頁畫好，這個工具只把片段塞進畫面的影片框、接上轉場，自己不畫任何文字。

## 安裝

### Windows 免安裝版

不必安裝 Python、ffmpeg 或 Deno，這些都包在裡面了。

1. 到 [GitHub Releases](https://github.com/ryrr6466/CRITShowCase/releases/latest) 下載 `critshowcase-<版本>-windows-x64.zip`（約 140 MB）。
2. 解壓到任何地方（解開後約 330 MB）。整個 `critshowcase` 資料夾要放在一起，不要只複製 `critshowcase.exe`。
3. 把網頁匯出的影片專案 zip 拖到 `critshowcase.exe` 上，就會開始出片；結束後視窗會停住，顯示成品位置或出錯原因，按 Enter 關閉。

- 第一次執行時 Windows 可能跳出「Windows 已保護您的電腦」（SmartScreen）：這個 exe 沒有程式碼簽章。按「其他資訊」→「仍要執行」即可。
- YouTube 常常改版。很多片段突然下載失敗時，到 Releases 下載最新版，解壓後取代舊的資料夾。片段快取不受影響。
- 下面「用法」的所有選項都能用：在命令列執行 `critshowcase.exe`，例如 `critshowcase.exe 匯出的.zip --cookies-from-browser firefox`。
- `licenses` 資料夾裡是隨附元件（ffmpeg、Deno、Python 與各套件）的授權文字。ffmpeg 以 GPL 授權，原始碼的取得方式見 `licenses/ffmpeg-SOURCE.txt`。

### 用 pip 安裝（macOS、Linux 與進階使用者）

需要：

- Python 3.10 以上
- [ffmpeg](https://ffmpeg.org/download.html)（`ffmpeg` 與 `ffprobe` 要能在命令列執行）
- [Deno](https://deno.com/) 或 [Node.js](https://nodejs.org/)：yt-dlp 要用它解 YouTube 的驗證，沒有的話很多片段會下載失敗

```bash
pip install git+https://github.com/ryrr6466/CRITShowCase.git
```

[yt-dlp](https://github.com/yt-dlp/yt-dlp)（含解 YouTube 驗證用的 yt-dlp-ejs）會一起裝好。YouTube 常常改版，下載失敗時先更新 yt-dlp：

```bash
pip install -U "yt-dlp[default]"
```

下載失敗、原因看不懂時，加上 `--verbose` 會印出 yt-dlp 的詳細訊息。回報問題時請附上 `critshowcase --version` 的輸出。

## 用法

```bash
critshowcase critlog-chunithm-b50-video.zip
```

- 輸入可以是網頁匯出的 zip，或解開後的 `project.json`。
- 成品預設放在輸入檔旁邊（`critlog-chunithm-b50-video.mp4`），用 `-o` 指定其他位置。
- 輸出 1920×1080、60 fps 的 H.264／AAC mp4。

### YouTube 要求登入驗證時

出現「YouTube 要求登入驗證」時，讓 yt-dlp 使用你瀏覽器的 cookies（瀏覽器要先登入 YouTube）：

```bash
critshowcase critlog-chunithm-b50-video.zip --cookies-from-browser firefox
```

也可以用 `--cookies cookies.txt` 指定匯出的 cookies 檔。詳見 yt-dlp 的 [FAQ](https://github.com/yt-dlp/yt-dlp/wiki/FAQ#how-do-i-pass-cookies-to-yt-dlp)。

- Windows 上的 Edge／Chrome 開著時會鎖住 cookie 資料庫，要先完全關閉（包含背景執行的程序）才讀得到；Firefox 沒有這個問題。
- 瀏覽器的 cookies 只在執行期間存成暫存檔，結束時就刪除。
- 讀不到 cookies，或用了 cookies 仍然被要求登入驗證時，工具會直接停下來，不會把每個片段都當成下載失敗。

### 片段快取

下載過的片段會依（影片 ID、開始秒數、長度）留在快取裡。回網頁改了評論、重新匯出後再執行一次，沒改過的片段不會重新下載。

| 系統 | 快取位置 |
|---|---|
| Windows | `%LOCALAPPDATA%\critshowcase\clips` |
| macOS | `~/Library/Caches/critshowcase/clips` |
| Linux | `$XDG_CACHE_HOME/critshowcase/clips`（預設 `~/.cache/critshowcase/clips`） |

- 想清除快取，直接刪掉這個資料夾即可。
- 加上 `--refresh` 會略過快取、重新下載所有片段（例如來源影片換過內容時）。
- 用「以系統管理員身分執行」的終端機跑過的話，那次存的快取檔，一般權限可能讀不到；工具會自動重新下載，不會失敗。
  想清掉這些檔案，要用系統管理員身分刪除快取資料夾。建議平常用一般權限執行就好。

### 下載失敗的片段

某個片段下載不到（影片被刪、設成私人、地區限制、網路錯誤）時，那一段改成靜態畫面＋靜音，整支影片照樣輸出，結束時列出是哪幾段。
回 CRITShowCase 頁面換掉這些片段、重新匯出後再執行一次即可。

| 結束碼 | 意思 |
|---|---|
| 0 | 完成 |
| 1 | 沒有輸出：影片專案不能用、找不到 ffmpeg／yt-dlp、讀不到 cookies、YouTube 要求登入驗證，或 ffmpeg 失敗 |
| 3 | 有輸出，但有片段下載失敗、改成靜態畫面 |

## 法律提醒

重新上傳別人的譜面影片，可能會被原作者或權利人申訴。這個工具只是讓下載發生在你自己的電腦上，不代表可以任意轉載；
請先確認來源頻道的轉載規定，或改用自己的手元影片（上傳成不公開影片後，在網頁上貼網址）。

這是非官方工具，與 SEGA 無關。畫面上的非官方標示不能拿掉。

## 開發

```bash
python -m venv .venv
.venv/Scripts/python -m pip install -e ".[test]"   # macOS／Linux 是 .venv/bin/python
.venv/Scripts/python -m mypy src
.venv/Scripts/python -m pytest
```

測試會實際呼叫 ffmpeg，不會連上 YouTube。

### 建置 Windows 免安裝版

```bash
.venv/Scripts/python -m pip install -e ".[build]"
.venv/Scripts/python packaging/build.py
.venv/Scripts/python packaging/smoke.py dist/critshowcase
```

- `build.py` 下載固定版本的 ffmpeg 與 Deno（網址與 sha256 寫在腳本裡，升級時手動改）、執行 PyInstaller，成品是 `dist/critshowcase-<版本>-windows-x64.zip`。
- `smoke.py` 在 PATH 上只有 Windows 系統資料夾的環境執行 exe，確認不靠你自己裝的工具也能出片。加上 `--youtube` 會實際下載一個 YouTube 片段（太常執行會被 YouTube 要求登入驗證）。
- 推 `v<版本>` tag（要跟 `pyproject.toml` 的版本一致）時，GitHub Actions 會建置、做煙霧測試，並把 zip 附到 Release；也可以在 Actions 頁面手動執行，只建置與測試。

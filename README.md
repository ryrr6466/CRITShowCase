# CRITShowCase

CRITShowCase（B50 影片）的出片工具。讀 [critlog.me](https://critlog.me) 的 CRITShowCase 頁面匯出的影片專案（zip），在你自己的電腦上下載需要的 YouTube 片段，合成一支 mp4。

每個段落的畫面（曲名、成績、評論、非官方標示）都由網頁畫好，這個工具只把片段塞進畫面的影片框、接上轉場，自己不畫任何文字。

## 安裝

### Windows 免安裝版

不必安裝 Python、ffmpeg 或 Deno，這些都包在裡面了。

1. 到 [GitHub Releases](https://github.com/ryrr6466/CRITShowCase/releases/latest) 下載 `critshowcase-<版本>-windows-x64.zip`（約 140 MB）。
2. 解壓到任何地方（解開後約 330 MB）。整個 `critshowcase` 資料夾要放在一起，不要只複製 `critshowcase.exe`。
3. 雙擊 `critshowcase-gui.exe` 打開視窗出片（見下面「用 GUI 出片」）。
   或是把網頁匯出的影片專案 zip 拖到 `critshowcase.exe` 上，就會開始出片；結束後視窗會停住，顯示成品位置或出錯原因，按 Enter 關閉。

- 第一次執行時 Windows 可能跳出「Windows 已保護您的電腦」（SmartScreen）：這個 exe 沒有程式碼簽章。按「其他資訊」→「仍要執行」即可。
- YouTube 常常改版。很多片段突然下載失敗時，到 Releases 下載最新版，解壓後取代舊的資料夾。片段快取不受影響。
- 下面「用法」的所有選項都能用：在命令列執行 `critshowcase.exe`，例如 `critshowcase.exe 匯出的.zip --cookies-from-browser firefox`。
- `licenses` 資料夾裡是隨附元件（ffmpeg、Deno、Python、Tcl／Tk 與各套件）的授權文字。ffmpeg 以 GPL 授權，原始碼的取得方式見 `licenses/ffmpeg-SOURCE.txt`。

### macOS 版（Apple Silicon）

1. 到 [GitHub Releases](https://github.com/ryrr6466/CRITShowCase/releases/latest) 下載 `critshowcase-<版本>-macos-arm64.zip`。
2. 雙擊解壓，把 `CRITShowCase.app` 拖到「應用程式」資料夾。
3. 打開 `CRITShowCase.app` 出片（見下面「用 GUI 出片」）；也可以把影片專案 zip 拖到 Dock 上的圖示。

- 需要 macOS 12 以上、Apple Silicon（M 系列）的 Mac。Intel Mac 請用 pip 安裝。
- app 有 Apple 的開發者簽章並經過公證，雙擊就能打開。
- 命令列版在 app 裡：`/Applications/CRITShowCase.app/Contents/MacOS/critshowcase 匯出的.zip`。
- 隨附元件的授權文字在解壓出來的 `licenses` 資料夾。ffmpeg 以 GPLv3 授權，原始碼的取得方式見 `licenses/ffmpeg-SOURCE.txt`。

### 用 pip 安裝（Intel Mac、Linux 與進階使用者）

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

## 用 GUI 出片

- Windows 免安裝版：雙擊 `critshowcase-gui.exe`；把影片專案 zip 拖到它的圖示上，會預先填好影片專案。
- macOS 版：打開 `CRITShowCase.app`；把影片專案 zip 拖到 app 或 Dock 上的圖示，會預先填好影片專案。
- pip 版：執行 `critshowcase-gui`。需要 Python 附的 tkinter；Linux 沒有的話要安裝 `python3-tk`。

1. 按「選擇…」選網頁匯出的影片專案。成品預設放在旁邊，按「另存為…」可以換位置。
2. YouTube 要求登入驗證時才需要 cookies：按「怎麼匯出 cookies？」照著教學匯出，再按「匯入 cookies.txt…」（見下面「在 GUI 匯入 cookies」）。
3. 按「開始出片」。進度條包含下載片段、合成段落、輸出 mp4；最後輸出 mp4 只有一步、沒有百分比，狀態文字會一直動。
4. 結束時會顯示成品位置與下載失敗的片段，按「開啟資料夾」找到成品。回報問題時，按「複製紀錄」貼上整段紀錄。

- 出片中關閉視窗會先確認。已經下載好的片段會留在快取，下次不必重新下載；沒輸出完的 mp4 不會留下。
- 跟拖到 `critshowcase.exe` 的差別：GUI 沒有黑色視窗、可以選輸出位置、記得匯入的 cookies。`--cookies-from-browser`、`--verbose` 等選項只有命令列版有。

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

#### 在 GUI 匯入 cookies

GUI 的「YouTube cookies」區塊按「怎麼匯出 cookies？」，會打開教學：安裝擴充功能、在無痕視窗登入 YouTube 後匯出 cookies.txt（從一般視窗匯出的 cookies 很快就會失效）。
匯出後按「匯入 cookies.txt…」，選匯出的檔案。匯入時會先檢查是不是 Netscape 格式、裡面有沒有 youtube.com 的 cookies，通過才留下來，之後出片都會自動使用。

- 匯入的是一份複本，原本下載資料夾裡的 cookies.txt 可以刪掉。cookies 等於你的 YouTube 登入狀態，不要傳給別人。
- 複本放在 `cookies.txt`，跟片段快取同一個 critshowcase 資料夾（Windows 是 `%LOCALAPPDATA%\critshowcase\cookies.txt`），但不在 `clips` 裡，刪快取不會刪到它。macOS 例外，放在 `~/Library/Application Support/critshowcase/cookies.txt`：`~/Library/Caches` 可能被系統或清理程式整個刪掉。按「清除」或直接刪掉這個檔案就不再使用。
- 只有 GUI 會用匯入的 cookies；命令列仍要自己加 `--cookies` 或 `--cookies-from-browser`。

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
- `smoke.py` 在 PATH 上只有 Windows 系統資料夾的環境執行 exe，確認不靠你自己裝的工具也能出片，並確認 `critshowcase-gui.exe` 開得出視窗（會跳出一秒後自己關掉）。加上 `--youtube` 會實際下載一個 YouTube 片段（太常執行會被 YouTube 要求登入驗證）。
- 推 `v<版本>` tag（要跟 `pyproject.toml` 的版本一致）時，GitHub Actions 會建置 Windows 與 macOS 版、做煙霧測試，並把兩個 zip 附到 Release；也可以在 Actions 頁面手動執行，只建置與測試。

### 建置 macOS 版

在 Apple Silicon 的 Mac 上用同樣的指令（`.venv/bin/python`）：`build.py` 建出 `dist/CRITShowCase/CRITShowCase.app` 與 `dist/critshowcase-<版本>-macos-arm64.zip`，`smoke.py` 的參數是 `dist/CRITShowCase`。

- ffmpeg 用 [martin-riedl.de](https://ffmpeg.martin-riedl.de/) 的 Apple Silicon release 建置，Deno 用官方的 `aarch64-apple-darwin` 版，都固定版本與 sha256。它們放在 `CRITShowCase.app/Contents/MacOS/tools`。
- 簽章與公證由環境變數控制。沒設定時只做 ad-hoc 簽章：自己的 Mac 上能跑，但別人下載後會被 Gatekeeper 擋下。

| 環境變數 | 內容 |
|---|---|
| `MACOS_SIGN_IDENTITY` | 簽章身分，例如 `Developer ID Application: 名字 (TEAMID)`（`security find-identity -v -p codesigning` 列得出來） |
| `NOTARY_PROFILE` | 本機用：`xcrun notarytool store-credentials` 存好的 profile 名稱 |
| `NOTARY_KEY`、`NOTARY_KEY_ID`、`NOTARY_ISSUER` | 或改用 App Store Connect API key：`.p8` 檔路徑、Key ID、Issuer ID |

GitHub Actions 從 repo secrets 取得憑證與 API key；推 tag 時沒有 secrets，macOS 那一份會失敗，不會發布沒簽章的版本。第一次設定：

1. 在 Mac 的「鑰匙圈存取」匯出 **Developer ID Application** 憑證（含私鑰）成 `.p12`，設一組密碼。沒有的話先到 Apple Developer 網站的 Certificates 建立。
2. 到 App Store Connect →「使用者與存取權限」→「整合」→ App Store Connect API 建立一把 key（存取權「開發者」即可），下載 `.p8`，記下 Key ID 與 Issuer ID。
3. 設定 secrets（在 repo 資料夾執行，`gh` 會提示輸入的值不會留在 shell 歷史）：

```bash
base64 -i DeveloperID.p12 | gh secret set MACOS_CERTIFICATE
gh secret set MACOS_CERTIFICATE_PASSWORD
base64 -i AuthKey_XXXXXXXXXX.p8 | gh secret set APPLE_API_KEY
gh secret set APPLE_API_KEY_ID
gh secret set APPLE_API_ISSUER_ID
```

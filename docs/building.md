# 建置與發布

免安裝版用 PyInstaller 打包，附上固定版本的 ffmpeg 與 Deno。在哪個平台執行 `build.py`，就建哪個平台的版本。

```bash
.venv/Scripts/python -m pip install -e ".[build]"   # macOS 是 .venv/bin/python
.venv/Scripts/python packaging/build.py
.venv/Scripts/python packaging/smoke.py dist/critshowcase   # macOS：dist/CRITShowCase
```

| 平台 | 成品 |
|---|---|
| Windows x64 | `dist/critshowcase/`、`dist/critshowcase-<版本>-windows-x64.zip` |
| macOS（Apple Silicon） | `dist/CRITShowCase/CRITShowCase.app`、`dist/critshowcase-<版本>-macos-arm64.zip` |

- `build.py` 下載固定版本的 ffmpeg 與 Deno。網址與 sha256 寫在腳本裡，升級時手動改。
- 下載的 zip 裡有 `licenses` 資料夾，收齊所有隨附元件的授權文字。
- `smoke.py` 在 PATH 上只有系統資料夾的環境執行成品，確認不靠你自己裝的工具也能出片，並確認 GUI 開得出視窗（會跳出一秒後自己關掉）。加上 `--youtube` 會實際下載一個 YouTube 片段（太常執行會被 YouTube 要求登入驗證）。

## 隨附的工具

| 工具 | Windows | macOS |
|---|---|---|
| ffmpeg 9.0.2 | [gyan.dev](https://www.gyan.dev/ffmpeg/builds/) 的 essentials 建置 | [martin-riedl.de](https://ffmpeg.martin-riedl.de/) 的 Apple Silicon release 建置 |
| Deno 2.9.7 | 官方 `x86_64-pc-windows-msvc` | 官方 `aarch64-apple-darwin` |

兩個 ffmpeg 都以 GPL 授權，含輸出要用的 libx264。macOS 那份的 zip 沒附授權文字，GPLv3 全文放在 `packaging/licenses/macos`。

## macOS 簽章與公證

簽章與公證由環境變數控制。沒設定時只做 ad-hoc 簽章：自己的 Mac 上能跑，但別人下載後會被 Gatekeeper 擋下。

| 環境變數 | 內容 |
|---|---|
| `MACOS_SIGN_IDENTITY` | 簽章身分，例如 `Developer ID Application: 名字 (TEAMID)`（`security find-identity -v -p codesigning` 列得出來） |
| `NOTARY_PROFILE` | 本機用：`xcrun notarytool store-credentials` 存好的 profile 名稱 |
| `NOTARY_KEY`、`NOTARY_KEY_ID`、`NOTARY_ISSUER` | 或改用 App Store Connect API key：`.p8` 檔路徑、Key ID、Issuer ID |

簽章時開啟 hardened runtime（公證的條件）。Python 與 Deno 需要的例外寫在 `packaging/macos` 的 entitlements。

## 發布

推 `v<版本>` tag 時（要跟 `pyproject.toml` 的版本一致），GitHub Actions 會建置 Windows 與 macOS 版、做煙霧測試，並把兩個 zip 附到 Release。也可以在 Actions 頁面手動執行，只建置與測試、不發布。

1. 在 PR 裡改 `pyproject.toml` 的版本，合併。
2. 在合併後的 commit 上打 tag 並推上去：

```bash
git tag -a v0.4.0 -m "v0.4.0"
git push origin v0.4.0
```

macOS 版從 repo secrets 取得憑證與 API key。推 tag 時沒有 secrets，macOS 那一份會失敗，不會發布沒簽章的版本。fork 的 repo 沒有這些 secrets：手動執行時只會建出 ad-hoc 簽章的測試版。

### 第一次設定 secrets

1. 在 Apple Developer 網站的 Certificates 建立 **Developer ID Application** 憑證（CSR 在 Mac 的「鑰匙圈存取」產生）。匯入後，從「鑰匙圈存取」連同私鑰匯出成 `.p12`，設一組密碼。
2. 到 App Store Connect →「使用者與存取權限」→「整合」→ App Store Connect API 建立一把 key（存取權「開發者」即可），下載 `.p8`，記下 Key ID 與 Issuer ID。
3. 設定 secrets：在 repo 的 Settings → Secrets and variables → Actions 新增，或在 repo 資料夾用 `gh` 設定（輸入的值不會留在 shell 歷史）：

```bash
base64 -i DeveloperID.p12 | gh secret set MACOS_CERTIFICATE
gh secret set MACOS_CERTIFICATE_PASSWORD
base64 -i AuthKey_XXXXXXXXXX.p8 | gh secret set APPLE_API_KEY
gh secret set APPLE_API_KEY_ID
gh secret set APPLE_API_ISSUER_ID
```

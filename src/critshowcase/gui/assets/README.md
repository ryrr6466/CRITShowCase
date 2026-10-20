# GUI 圖片

取自 CRITLOG App repo（`ryrr6466/CRITLOG`）的 `docs/design/brand`，用 Pillow 縮成固定尺寸；Tk 只能整數倍縮放，所以先縮好。

| 檔案 | 來源 | 用途 |
|---|---|---|
| `wordmark-dark.png`、`wordmark-dark@2x.png` | `critlog-wordmark-dark.png` 縮成寬 240、480 | 標題列的字標；縮放 150% 以上用 @2x |
| `icon-16.png`～`icon-256.png` | `critlog-icon-1024.png` | 視窗與工作列的 icon |
| `packaging/critshowcase.ico` | `critlog-icon-1024.png`（16～256） | 兩個 exe 在檔案總管的圖示 |

品牌素材改版時，從那邊的母版重新匯出同樣的檔名與尺寸。

"""教學視窗：安裝擴充功能，在無痕視窗登入 YouTube 後匯出 cookies.txt。

步驟依 yt-dlp wiki 的 FAQ（How do I pass cookies to yt-dlp）與 Extractors（Exporting YouTube cookies）。
瀏覽器或 YouTube 改版時，只要改這個檔案上半部的 BROWSERS 與 COMMON。
"""
from __future__ import annotations

import sys
import tkinter as tk
import webbrowser
from collections.abc import Callable
from dataclasses import dataclass
from tkinter import font, ttk

from critshowcase.gui import theme
from critshowcase.gui.theme import px

ROBOTS = "https://www.youtube.com/robots.txt"
WIKI = "https://github.com/yt-dlp/yt-dlp/wiki/Extractors#exporting-youtube-cookies"


@dataclass(frozen=True)
class Browser:
    tab: str
    extension: str
    store_url: str
    # 這個瀏覽器怎麼稱呼無痕視窗、怎麼打開
    private_window: str
    shortcut: str
    # 讓擴充功能可以在無痕視窗執行
    allow_private: str
    warning: str | None = None


BROWSERS = [
    Browser(
        tab="Chrome／Edge",
        extension="Get cookies.txt LOCALLY",
        store_url="https://chrome.google.com/webstore/detail/get-cookiestxt-locally/cclelndahbckbenkjhflpdbgdldlbecc",
        private_window="無痕視窗（Edge 叫 InPrivate 視窗）",
        shortcut="Ctrl+Shift+N",
        allow_private=(
            "Chrome：在網址列輸入 chrome://extensions，找到 Get cookies.txt LOCALLY 按「詳細資料」，開啟「在無痕模式中允許」。\n"
            "Edge：在網址列輸入 edge://extensions，找到 Get cookies.txt LOCALLY 按「詳細資料」，勾選「在 InPrivate 中允許」。"
        ),
        warning=(
            "請認明名稱最後有 LOCALLY。另一個名字只差一個字的「Get cookies.txt」被回報是惡意程式、已經從商店下架；"
            "以前裝過的話請立刻移除。Edge 也可以直接從 Chrome 線上應用程式商店安裝（第一次會問要不要允許其他商店的擴充功能）。"
        ),
    ),
    Browser(
        tab="Firefox",
        extension="cookies.txt",
        store_url="https://addons.mozilla.org/firefox/addon/cookies-txt/",
        private_window="隱私視窗",
        shortcut="Ctrl+Shift+P",
        allow_private="打開「附加元件與佈景主題」（Ctrl+Shift+A），點 cookies.txt，在「在隱私視窗中執行」選「允許」。",
    ),
]

COMMON = {
    "why": (
        "為什麼要用無痕視窗？YouTube 會一直更換一般視窗裡的登入 cookies，從一般視窗匯出的 cookies 很快就會失效。"
        "在無痕視窗登入、匯出後立刻關掉，那組 cookies 就不會再被瀏覽器換掉，可以用比較久。"
    ),
    "account": "建議用分身帳號登入：YouTube 可能會暫時或永久停用被拿來下載影片的帳號。",
    "secret": "cookies.txt 等於你的 YouTube 登入狀態，拿到它的人就能用你的帳號。不要傳給別人，匯入後可以把原始檔刪掉。",
    "expired": "之後又出現「YouTube 要求登入驗證」，就是 cookies 失效了，照同樣的步驟重新匯出、匯入一次即可。",
}


def steps(browser: Browser, platform: str = sys.platform) -> list[str]:
    """編號步驟；網址以 {link:文字|網址} 標出。快捷鍵照 Windows 寫，macOS 換成 Cmd。"""
    lines = [
        f"安裝擴充功能「{browser.extension}」：{{link:打開擴充功能頁面|{browser.store_url}}}",
        f"讓它可以在{browser.private_window}執行。\n{browser.allow_private}",
        f"開一個新的{browser.private_window}（{browser.shortcut}），登入 YouTube。先把其他{browser.private_window}都關掉。",
        f"在同一個分頁打開 {{link:{ROBOTS}|{ROBOTS}}}，停在這一頁；{browser.private_window}裡只留這一個分頁。",
        f"點瀏覽器右上角的「{browser.extension}」擴充功能，匯出目前網站（youtube.com）的 cookies，存成 cookies.txt。",
        f"立刻關掉整個{browser.private_window}，之後不要再打開這個登入工作階段。",
        "回到這裡匯入 cookies.txt：",
    ]
    if platform == "darwin":
        return [line.replace("Ctrl+", "Cmd+") for line in lines]
    return lines


class TutorialWindow:
    def __init__(self, parent: tk.Misc, on_import: Callable[[tk.Misc], None]) -> None:
        self.window = tk.Toplevel(parent)
        self.window.title("怎麼匯出 YouTube cookies")
        self.window.geometry(f"{px(660)}x{px(640)}")
        self.window.minsize(px(480), px(400))
        self.window.configure(background=theme.BG)
        self.on_import = on_import
        notebook = ttk.Notebook(self.window, padding=px(12))
        notebook.pack(fill="both", expand=True)
        for browser in BROWSERS:
            notebook.add(self._page(notebook, browser), text=browser.tab)

    def lift(self) -> None:
        self.window.deiconify()
        self.window.lift()
        self.window.focus_set()

    def exists(self) -> bool:
        return bool(self.window.winfo_exists())

    def _page(self, parent: ttk.Notebook, browser: Browser) -> ttk.Frame:
        page = ttk.Frame(parent, style="Card.TFrame", padding=1)
        page.columnconfigure(0, weight=1)
        page.rowconfigure(0, weight=1)
        base = font.nametofont("TkDefaultFont")
        text = tk.Text(
            page,
            wrap="word",
            padx=px(20),
            pady=px(16),
            relief="flat",
            borderwidth=0,
            highlightthickness=0,
            background=theme.CARD,
            foreground=theme.TEXT,
            font=base,
            cursor="arrow",
            spacing1=px(2),
            spacing3=px(6),
        )
        text.grid(row=0, column=0, sticky="nsew")
        scrollbar = ttk.Scrollbar(page, orient="vertical", command=text.yview)
        scrollbar.grid(row=0, column=1, sticky="ns")
        text.configure(yscrollcommand=scrollbar.set)
        bold = base.copy()
        bold.configure(weight="bold")
        heading = base.copy()
        heading.configure(weight="bold", size=base.actual("size") + 2)
        text.tag_configure("heading", font=heading, spacing3=px(10))
        text.tag_configure("number", font=bold, foreground=theme.ACCENT)
        # 步驟換行時對齊編號後面的文字
        text.tag_configure("step", lmargin2=px(22))
        text.tag_configure("substep", lmargin1=px(22), lmargin2=px(22))
        text.tag_configure("warning", foreground=theme.DANGER)
        text.tag_configure("note", foreground=theme.MUTED)
        text.tag_configure("link", foreground=theme.LINK, underline=True)
        text.tag_bind("link", "<Enter>", lambda event: text.configure(cursor="hand2"))
        text.tag_bind("link", "<Leave>", lambda event: text.configure(cursor="arrow"))

        text.insert("end", "YouTube 要求登入驗證時，用瀏覽器擴充功能匯出 cookies.txt，再匯入 CRITShowCase。\n", "heading")
        text.insert("end", COMMON["why"] + "\n\n", "note")
        if browser.warning:
            text.insert("end", "⚠ " + browser.warning + "\n\n", "warning")
        for number, step in enumerate(steps(browser), start=1):
            start = text.index("end-1c")
            text.insert("end", f"{number}. ", "number")
            self._insert_with_links(text, step)
            text.insert("end", "\n")
            text.tag_add("step", start, "end-1c")
            # 步驟裡換行的段落（例如 Chrome、Edge 各一行）整段縮排
            first, last = int(start.split(".")[0]), int(text.index("end-1c").split(".")[0]) - 1
            for line in range(first + 1, last + 1):
                text.tag_add("substep", f"{line}.0", f"{line}.end")
        button = ttk.Button(text, text="匯入 cookies.txt…", command=lambda: self.on_import(self.window))
        text.window_create("end", window=button, padx=px(22))
        text.insert("end", "\n\n")
        for key in ("account", "secret", "expired"):
            text.insert("end", "・" + COMMON[key] + "\n", "note")
        text.insert("end", "\n詳細說明（英文）：", "note")
        self._insert_with_links(text, f"{{link:yt-dlp wiki|{WIKI}}}")
        text.configure(state="disabled")
        return page

    def _insert_with_links(self, text: tk.Text, line: str) -> None:
        rest = line
        while "{link:" in rest:
            before, _, after = rest.partition("{link:")
            label_url, _, rest = after.partition("}")
            label, _, url = label_url.partition("|")
            text.insert("end", before)
            tag = f"url-{text.index('end')}"
            text.insert("end", label, ("link", tag))
            text.tag_bind(tag, "<Button-1>", _opener(url))
        text.insert("end", rest)


def _opener(url: str) -> Callable[[tk.Event[tk.Misc]], None]:
    def open_url(event: tk.Event[tk.Misc]) -> None:
        webbrowser.open(url)

    return open_url

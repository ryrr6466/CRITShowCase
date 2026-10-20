"""視窗的配色、字型與 ttk 樣式。

以 clam 為底（各平台長得一樣、顏色都改得動），主視窗與教學視窗共用。
間距一律寫成 96 DPI 下的像素，經過 px() 換算，高 DPI 螢幕上才不會擠在一起。
"""
from __future__ import annotations

import tkinter as tk
from tkinter import font, ttk

BG = "#f3f5f9"
CARD = "#ffffff"
BORDER = "#dde2ea"
FIELD = "#f7f8fb"
TEXT = "#1f2633"
MUTED = "#6b7482"
HEADER = "#1b2130"
HEADER_MUTED = "#a3adc2"
ACCENT = "#4361ee"
ACCENT_HOVER = "#3550d6"
ACCENT_PRESSED = "#2a41b5"
ACCENT_DISABLED = "#b6c0f2"
SUCCESS = "#1a9a57"
DANGER = "#b42318"
DANGER_BG = "#fef3f2"
LINK = "#0b57d0"

# 有的話用微軟正黑體：Windows 預設字型配中文時字距、粗細都不一致
FAMILIES = ("Microsoft JhengHei UI", "PingFang TC", "Noto Sans CJK TC")

_scale = 1.0
_kept: list[font.Font] = []


def px(pixels: float) -> int:
    """96 DPI 下的像素 → 這個螢幕上的像素。"""
    return round(pixels * _scale)


def apply(root: tk.Misc) -> None:
    global _scale
    _scale = max(1.0, root.winfo_fpixels("1i") / 96)
    _fonts(root)
    style = ttk.Style(root)
    style.theme_use("clam")
    _base(style)
    _buttons(style)
    _fields(style)
    _containers(style)
    root.configure(background=BG)  # type: ignore[call-arg]


def _fonts(root: tk.Misc) -> None:
    available = set(font.families(root))
    family = next((name for name in FAMILIES if name in available), None)
    for name in ("TkDefaultFont", "TkTextFont", "TkMenuFont", "TkHeadingFont"):
        named = font.nametofont(name, root)
        if family:
            named.configure(family=family)
        named.configure(size=10)
    base = font.nametofont("TkDefaultFont", root)
    _named(root, "CritTitle", base, size=17, weight="bold")
    _named(root, "CritSubtitle", base, size=10)
    _named(root, "CritHeading", base, size=11, weight="bold")
    _named(root, "CritSmall", base, size=9)
    _named(root, "CritButton", base, size=11, weight="bold")
    _named(root, "CritUnderline", base, underline=True)


def _named(root: tk.Misc, name: str, base: font.Font, **options: object) -> None:
    """建立或更新具名字型；樣式用名字指定字型，之後改字型不必重設樣式。"""
    # 不用 base.actual()：Windows 上它回傳的字型名稱拿來建字型會找不到，退回成明體
    settings = {"family": base.cget("family"), "size": base.cget("size"), "weight": "normal", "underline": False, **options}
    if name in font.names(root):
        font.nametofont(name, root).configure(**settings)  # type: ignore[arg-type]
    else:
        # Font 物件被回收時 Tk 會一起刪掉這個具名字型，要留著參照
        _kept.append(font.Font(root, name=name, **settings))  # type: ignore[arg-type]


def _base(style: ttk.Style) -> None:
    style.configure(".", background=BG, foreground=TEXT, bordercolor=BORDER, lightcolor=BG, darkcolor=BG, focuscolor=ACCENT, troughcolor=BG)
    style.configure("TLabel", background=BG)
    style.configure("Muted.TLabel", foreground=MUTED, font="CritSmall")
    style.configure("Status.TLabel", font="CritHeading")
    style.configure("Percent.TLabel", foreground=ACCENT, font="CritHeading")
    style.configure("Header.TFrame", background=HEADER)
    style.configure("Title.TLabel", background=HEADER, foreground="#ffffff", font="CritTitle")
    style.configure("Subtitle.TLabel", background=HEADER, foreground=HEADER_MUTED, font="CritSubtitle")
    style.configure("Accent.TFrame", background=ACCENT)
    style.configure("Card.TFrame", background=CARD, bordercolor=BORDER, lightcolor=CARD, darkcolor=CARD, relief="solid", borderwidth=1)
    style.configure("Card.TLabel", background=CARD)
    style.configure("CardHeading.TLabel", background=CARD, font="CritHeading")
    style.configure("CardMuted.TLabel", background=CARD, foreground=MUTED, font="CritSmall")
    style.configure("Ok.TLabel", background=CARD, foreground=SUCCESS)
    style.configure("Off.TLabel", background=CARD, foreground="#b3bac6")


def _buttons(style: ttk.Style) -> None:
    style.configure(
        "TButton",
        background=CARD,
        foreground=TEXT,
        bordercolor=BORDER,
        lightcolor=CARD,
        darkcolor=CARD,
        focuscolor=CARD,
        padding=(px(12), px(5)),
        anchor="center",
    )
    style.map(
        "TButton",
        background=[("disabled", BG), ("pressed", "#e3e7ef"), ("active", "#eef1f7")],
        lightcolor=[("disabled", BG), ("pressed", "#e3e7ef"), ("active", "#eef1f7")],
        darkcolor=[("disabled", BG), ("pressed", "#e3e7ef"), ("active", "#eef1f7")],
        foreground=[("disabled", "#a7aebb")],
        bordercolor=[("focus", ACCENT)],
    )
    accent = {"background": ACCENT, "lightcolor": ACCENT, "darkcolor": ACCENT, "bordercolor": ACCENT, "focuscolor": ACCENT}
    style.configure("Accent.TButton", foreground="#ffffff", font="CritButton", padding=(px(28), px(9)), **accent)
    states = [("disabled", ACCENT_DISABLED), ("pressed", ACCENT_PRESSED), ("active", ACCENT_HOVER)]
    style.map(
        "Accent.TButton",
        background=states,
        lightcolor=states,
        darkcolor=states,
        bordercolor=states,
        foreground=[("disabled", "#ffffff")],
    )
    # 長得像連結的按鈕
    flat = {"background": CARD, "lightcolor": CARD, "darkcolor": CARD, "bordercolor": CARD, "focuscolor": CARD}
    style.configure("Link.TButton", foreground=LINK, padding=(px(4), px(5)), **flat)
    style.map(
        "Link.TButton",
        background=[("active", CARD)],
        lightcolor=[("active", CARD)],
        darkcolor=[("active", CARD)],
        bordercolor=[("focus", CARD)],
        foreground=[("pressed", ACCENT_PRESSED), ("active", ACCENT_HOVER)],
        font=[("active", "CritUnderline")],
    )


def _fields(style: ttk.Style) -> None:
    style.configure(
        "TEntry",
        fieldbackground=FIELD,
        foreground=TEXT,
        bordercolor=BORDER,
        lightcolor=FIELD,
        darkcolor=FIELD,
        padding=(px(8), px(6)),
    )
    style.map("TEntry", fieldbackground=[("readonly", FIELD)], lightcolor=[("readonly", FIELD)], darkcolor=[("readonly", FIELD)])
    style.configure(
        "TCheckbutton",
        background=BG,
        indicatorbackground=CARD,
        indicatorforeground="#ffffff",
        upperbordercolor="#b9c0cc",
        lowerbordercolor="#b9c0cc",
        indicatormargin=(0, 0, px(8), 0),
        focuscolor=BG,
    )
    style.map(
        "TCheckbutton",
        background=[("active", BG)],
        indicatorbackground=[("disabled", BG), ("selected", ACCENT)],
        upperbordercolor=[("selected", ACCENT)],
        lowerbordercolor=[("selected", ACCENT)],
        foreground=[("disabled", "#a7aebb")],
    )
    style.configure(
        "Accent.Horizontal.TProgressbar",
        background=ACCENT,
        troughcolor="#e3e7f0",
        bordercolor="#e3e7f0",
        lightcolor=ACCENT,
        darkcolor=ACCENT,
        thickness=px(10),
    )


def _containers(style: ttk.Style) -> None:
    style.configure(
        "Vertical.TScrollbar",
        background="#cfd5df",
        troughcolor=CARD,
        bordercolor=CARD,
        lightcolor="#cfd5df",
        darkcolor="#cfd5df",
        arrowcolor=MUTED,
        gripcount=0,
        arrowsize=px(12),
    )
    style.map(
        "Vertical.TScrollbar",
        background=[("active", "#b4bcc9")],
        lightcolor=[("active", "#b4bcc9")],
        darkcolor=[("active", "#b4bcc9")],
    )
    style.configure("TNotebook", background=BG, borderwidth=0, tabmargins=(px(8), px(8), px(8), 0))
    style.configure(
        "TNotebook.Tab",
        background="#e6e9f0",
        foreground=MUTED,
        bordercolor=BORDER,
        lightcolor="#e6e9f0",
        darkcolor="#e6e9f0",
        padding=(px(16), px(6)),
        focuscolor="#e6e9f0",
    )
    style.map(
        "TNotebook.Tab",
        background=[("selected", CARD)],
        lightcolor=[("selected", CARD)],
        darkcolor=[("selected", CARD)],
        foreground=[("selected", TEXT)],
        focuscolor=[("selected", CARD)],
    )

"""主視窗：選影片專案 → 出片 → 進度條 → 結果。

出片工作在背景執行緒跑；tkinter 不是 thread-safe，背景執行緒只把進度事件與結果丟進 queue，
由主執行緒定時取出來更新畫面。
"""
from __future__ import annotations

import queue
import subprocess
import sys
import threading
import tkinter as tk
import webbrowser
from datetime import datetime
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from types import TracebackType

from critshowcase import package_version
from critshowcase.cookies import CookieError, CookieStore
from critshowcase.download import RELEASES
from critshowcase.gui import theme
from critshowcase.gui.theme import px
from critshowcase.gui.tutorial import TutorialWindow
from critshowcase.job import JobResult, default_output, run_job
from critshowcase.render import Progress

TITLE = "CRITShowCase 出片工具"
POLL_MS = 100
DOTS_MS = 500


class App:
    def __init__(self, root: tk.Tk, source: Path | None = None, cookie_store: CookieStore | None = None) -> None:
        self.root = root
        self.cookie_store = cookie_store or CookieStore()
        self.events: queue.Queue[Progress | JobResult] = queue.Queue()
        self.worker: threading.Thread | None = None
        self.last_output: Path | None = None
        # 輸出 mp4 時讓狀態文字動著的 after() 排程
        self.dots_job: str | None = None
        self.used_cookies = False
        self.tutorial: TutorialWindow | None = None
        self.source = tk.StringVar()
        self.output = tk.StringVar()
        self.refresh = tk.BooleanVar()
        self.status = tk.StringVar(value="選擇影片專案後，按「開始出片」。")
        self.percent = tk.StringVar()
        self.cookie_status = tk.StringVar()
        theme.apply(root)
        theme.set_icon(root)
        root.title(TITLE)
        root.geometry(f"{px(720)}x{px(700)}")
        root.minsize(px(600), px(600))
        root.protocol("WM_DELETE_WINDOW", self._close)
        root.report_callback_exception = self._report_error  # type: ignore[method-assign]
        self._build()
        if source:
            self._set_source(Path(source))
        self._update_controls()
        if sys.platform == "darwin":
            # 把檔案拖到 Dock 或 Finder 裡的 app 圖示上時，macOS 送的是 Apple Event，不是命令列參數
            root.createcommand("::tk::mac::OpenDocument", self._open_documents)
            # Cmd+Q 也要經過「還沒輸出完成」的確認
            root.createcommand("::tk::mac::Quit", self._close)

    # ---- 版面 ----

    def _build(self) -> None:
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(1, weight=1)
        self._build_header()
        frame = ttk.Frame(self.root, padding=(px(20), px(16), px(20), px(14)))
        frame.grid(row=1, column=0, sticky="nsew")
        frame.columnconfigure(0, weight=1)

        files = self._card(frame, 0, "檔案")
        files.columnconfigure(1, weight=1)
        ttk.Label(files, text="影片專案", style="Card.TLabel").grid(row=0, column=0, sticky="w", padx=(0, px(12)))
        ttk.Entry(files, textvariable=self.source, state="readonly").grid(row=0, column=1, sticky="ew")
        self.choose_source = ttk.Button(files, text="選擇…", command=self._choose_source)
        self.choose_source.grid(row=0, column=2, padx=(px(8), 0))
        ttk.Label(files, text="網頁匯出的 zip 或 project.json；也可以把 zip 拖到程式圖示上打開。", style="CardMuted.TLabel").grid(
            row=1, column=1, columnspan=2, sticky="w", pady=(px(4), px(10))
        )
        ttk.Label(files, text="輸出 mp4", style="Card.TLabel").grid(row=2, column=0, sticky="w", padx=(0, px(12)))
        ttk.Entry(files, textvariable=self.output, state="readonly").grid(row=2, column=1, sticky="ew")
        self.choose_output = ttk.Button(files, text="另存為…", command=self._choose_output)
        self.choose_output.grid(row=2, column=2, padx=(px(8), 0))

        cookies = self._card(frame, 1, "YouTube cookies")
        cookies.columnconfigure(3, weight=1)
        status = ttk.Frame(cookies, style="Card.TFrame", borderwidth=0)
        status.grid(row=0, column=0, columnspan=4, sticky="w")
        self.cookie_dot = ttk.Label(status, text="●", style="Off.TLabel")
        self.cookie_dot.grid(row=0, column=0, padx=(0, px(6)))
        ttk.Label(status, textvariable=self.cookie_status, style="Card.TLabel").grid(row=0, column=1, sticky="w")
        self.import_cookies = ttk.Button(cookies, text="匯入 cookies.txt…", command=self._import_cookies)
        self.import_cookies.grid(row=1, column=0, sticky="w", pady=(px(10), 0))
        self.clear_cookies = ttk.Button(cookies, text="清除", command=self._clear_cookies)
        self.clear_cookies.grid(row=1, column=1, padx=(px(8), 0), pady=(px(10), 0))
        ttk.Button(cookies, text="怎麼匯出 cookies？", style="Link.TButton", command=self._show_tutorial).grid(
            row=1, column=3, sticky="e", pady=(px(10), 0)
        )

        actions = ttk.Frame(frame)
        actions.grid(row=2, column=0, sticky="ew", pady=(px(14), 0))
        actions.columnconfigure(0, weight=1)
        self.refresh_box = ttk.Checkbutton(actions, text="不用快取，所有片段重新下載", variable=self.refresh)
        self.refresh_box.grid(row=0, column=0, sticky="w")
        self.start = ttk.Button(actions, text="開始出片", style="Accent.TButton", command=self._start)
        self.start.grid(row=0, column=1, sticky="e")

        progress = ttk.Frame(frame)
        progress.grid(row=3, column=0, sticky="ew", pady=(px(16), 0))
        progress.columnconfigure(0, weight=1)
        ttk.Label(progress, textvariable=self.status, style="Status.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Label(progress, textvariable=self.percent, style="Percent.TLabel").grid(row=0, column=1, sticky="e")
        self.progress = ttk.Progressbar(progress, mode="determinate", maximum=1, style="Accent.Horizontal.TProgressbar")
        self.progress.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(px(6), 0))

        log = ttk.Frame(frame, style="Card.TFrame", padding=1)
        log.grid(row=4, column=0, sticky="nsew", pady=(px(12), 0))
        frame.rowconfigure(4, weight=1)
        log.columnconfigure(0, weight=1)
        log.rowconfigure(0, weight=1)
        self.log = tk.Text(
            log,
            height=8,
            wrap="word",
            state="disabled",
            font="CritSmall",
            background=theme.CARD,
            foreground=theme.TEXT,
            relief="flat",
            borderwidth=0,
            highlightthickness=0,
            padx=px(10),
            pady=px(8),
            spacing3=px(2),
        )
        self.log.grid(row=0, column=0, sticky="nsew")
        self.log.tag_configure("time", foreground=theme.MUTED)
        self.log.tag_configure("error", foreground=theme.DANGER)
        self.log.tag_configure("success", foreground=theme.SUCCESS)
        scrollbar = ttk.Scrollbar(log, orient="vertical", command=self.log.yview)
        scrollbar.grid(row=0, column=1, sticky="ns")
        self.log.configure(yscrollcommand=scrollbar.set)

        bottom = ttk.Frame(frame)
        bottom.grid(row=5, column=0, sticky="ew", pady=(px(10), 0))
        bottom.columnconfigure(0, weight=1)
        versions = f"critshowcase {package_version('critshowcase')}　·　yt-dlp {package_version('yt-dlp')}"
        ttk.Label(bottom, text=versions, style="Muted.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Button(bottom, text="複製紀錄", command=self._copy_log).grid(row=0, column=1, padx=(px(8), 0))
        self.open_folder = ttk.Button(bottom, text="開啟資料夾", command=self._open_folder)
        self.open_folder.grid(row=0, column=2, padx=(px(8), 0))

    def _build_header(self) -> None:
        header = ttk.Frame(self.root, style="Header.TFrame", padding=(px(20), px(16), px(20), px(16)))
        header.grid(row=0, column=0, sticky="ew")
        ttk.Label(header, image=theme.wordmark(self.root), style="Title.TLabel").grid(row=0, column=0, rowspan=2, sticky="w")
        ttk.Frame(header, style="Divider.TFrame", width=1).grid(row=0, column=1, rowspan=2, sticky="ns", padx=px(16))
        ttk.Label(header, text="ShowCase 出片工具", style="Title.TLabel").grid(row=0, column=2, sticky="sw")
        ttk.Label(header, text="把網頁匯出的 B50 影片專案合成 mp4", style="Subtitle.TLabel").grid(row=1, column=2, sticky="nw")
        theme.trail(self.root, px(3)).grid(row=0, column=0, sticky="sew")

    def _card(self, parent: ttk.Frame, row: int, title: str) -> ttk.Frame:
        """白底卡片：標題在上，回傳放內容的 frame。"""
        card = ttk.Frame(parent, style="Card.TFrame", padding=(px(16), px(12), px(16), px(14)))
        card.grid(row=row, column=0, sticky="ew", pady=(0 if row == 0 else px(12), 0))
        card.columnconfigure(0, weight=1)
        ttk.Label(card, text=title, style="CardHeading.TLabel").grid(row=0, column=0, sticky="w", pady=(0, px(10)))
        body = ttk.Frame(card, style="Card.TFrame", borderwidth=0)
        body.grid(row=1, column=0, sticky="ew")
        return body

    def _update_controls(self) -> None:
        busy = self.worker is not None
        state = "disabled" if busy else "normal"
        for widget in (self.choose_source, self.choose_output, self.refresh_box, self.import_cookies):
            widget.configure(state=state)
        imported = self.cookie_store.current()
        self.clear_cookies.configure(state="normal" if not busy and imported else "disabled")
        if imported:
            self.cookie_status.set(f"已匯入（{imported.imported_at:%Y-%m-%d %H:%M}），出片時會使用。")
        else:
            self.cookie_status.set("未匯入。YouTube 要求登入驗證時才需要。")
        self.cookie_dot.configure(style="Ok.TLabel" if imported else "Off.TLabel")
        self.start.configure(state="normal" if not busy and self.source.get() else "disabled")
        self.open_folder.configure(state="normal" if not busy and self.last_output else "disabled")

    # ---- 選檔 ----

    def _choose_source(self) -> None:
        path = filedialog.askopenfilename(
            parent=self.root,
            title="選擇影片專案",
            filetypes=[("影片專案", "*.zip *.json"), ("所有檔案", "*.*")],
        )
        if path:
            self._set_source(Path(path))
            self._update_controls()

    def _set_source(self, source: Path) -> None:
        self.source.set(str(source))
        self.output.set(str(default_output(source)))

    def _open_documents(self, *paths: str) -> None:
        """拖了好幾個檔案時只取第一個；出片中不換影片專案。"""
        if self.worker is not None:
            messagebox.showinfo(TITLE, "出片中不能換影片專案，請等這次出片結束。", parent=self.root)
            return
        if paths:
            self._set_source(Path(paths[0]))
            self._update_controls()
            self.root.lift()

    def _choose_output(self) -> None:
        current = Path(self.output.get()) if self.output.get() else None
        path = filedialog.asksaveasfilename(
            parent=self.root,
            title="輸出 mp4",
            defaultextension=".mp4",
            filetypes=[("mp4 影片", "*.mp4")],
            initialdir=str(current.parent) if current else None,
            initialfile=current.name if current else None,
        )
        if path:
            self.output.set(path)

    # ---- cookies ----

    def _import_cookies(self, parent: tk.Misc | None = None) -> None:
        """parent：從教學視窗按匯入時，對話框跳在教學視窗上面。"""
        parent = parent or self.root
        # 教學視窗裡也有匯入按鈕；出片中不換 cookies
        if self.worker is not None:
            messagebox.showinfo(TITLE, "出片中不能匯入 cookies，請等這次出片結束。", parent=parent)
            return
        path = filedialog.askopenfilename(
            parent=parent,
            title="選擇匯出的 cookies.txt",
            filetypes=[("cookies.txt", "*.txt"), ("所有檔案", "*.*")],
        )
        if not path:
            return
        try:
            self.cookie_store.import_file(Path(path))
        except CookieError as error:
            messagebox.showerror(TITLE, f"沒有匯入：{error}", parent=parent)
            return
        self._update_controls()
        self._log("已匯入 cookies。")
        messagebox.showinfo(
            TITLE,
            "已匯入 cookies，之後出片都會使用。\n\n"
            f"原本的 {Path(path).name} 可以刪掉了：cookies 等於你的 YouTube 登入狀態，不要留在下載資料夾或傳給別人。",
            parent=parent,
        )

    def _clear_cookies(self) -> None:
        if messagebox.askyesno(TITLE, "要刪除匯入的 cookies 嗎？", parent=self.root):
            self.cookie_store.clear()
            self._update_controls()
            self._log("已清除 cookies。")

    def _show_tutorial(self) -> None:
        if self.tutorial is None or not self.tutorial.exists():
            self.tutorial = TutorialWindow(self.root, on_import=self._import_cookies)
        self.tutorial.lift()

    def _blocked_message(self, error: str, used_cookies: bool) -> str:
        if used_cookies:
            return (
                "用了匯入的 cookies，YouTube 仍然要求登入驗證，或 cookies 讀不了：cookies 可能已經失效。\n"
                "請重新匯出 cookies.txt、匯入後再出片一次。\n\n"
                f"詳細原因：{error}"
            )
        return (
            "YouTube 要求登入驗證，這台電腦目前無法下載。\n"
            "請用瀏覽器擴充功能匯出 YouTube 的 cookies.txt，按「匯入 cookies.txt…」匯入後再出片一次。"
        )

    # ---- 出片 ----

    def _start(self) -> None:
        source, output = Path(self.source.get()), Path(self.output.get())
        self.last_output = None
        self.progress.configure(value=0, maximum=1)
        self.percent.set("0%")
        self._log(f"開始出片：{source}")
        self.status.set("準備中…")
        imported = self.cookie_store.current()
        self.used_cookies = imported is not None
        args = (source, output, imported.path if imported else None, self.refresh.get())
        self.worker = threading.Thread(target=self._work, args=args, daemon=True)
        self.worker.start()
        self._update_controls()
        self.root.after(POLL_MS, self._poll)

    def _work(self, source: Path, output: Path, cookies: Path | None, refresh: bool) -> None:
        """背景執行緒：不碰任何 widget。"""
        try:
            result = run_job(source, output, cookies=cookies, refresh=refresh, progress=self.events.put)
        except Exception as error:  # 沒預料到的錯誤也要回報，不然視窗會一直停在出片中
            result = JobResult(error=f"發生沒有預料到的錯誤：{error!r}")
        self.events.put(result)

    def _poll(self) -> None:
        while True:
            try:
                event = self.events.get_nowait()
            except queue.Empty:
                break
            if isinstance(event, JobResult):
                self._finish(event)
                return
            self._show_progress(event)
        self.root.after(POLL_MS, self._poll)

    def _show_progress(self, event: Progress) -> None:
        self.progress.configure(maximum=event.steps, value=event.done)
        self.percent.set(f"{event.done * 100 // event.steps}%")
        if event.stage == "done":
            return
        self.status.set(event.message)
        self._log(event.message)
        # 輸出 mp4 只有一步但可能很久：不假裝知道百分比，讓狀態文字動著，看得出還在跑
        if event.stage == "join" and self.dots_job is None:
            self._animate_dots(0)

    def _animate_dots(self, count: int) -> None:
        self.status.set("輸出 mp4" + "." * (count % 4))
        self.dots_job = self.root.after(DOTS_MS, self._animate_dots, count + 1)

    def _finish(self, result: JobResult) -> None:
        self.worker = None
        if self.dots_job is not None:
            self.root.after_cancel(self.dots_job)
            self.dots_job = None
        if result.error is not None:
            # 被要求登入驗證時，原本的訊息教的是命令列選項；GUI 改說匯入 cookies
            message = self._blocked_message(result.error, self.used_cookies) if result.blocked else result.error
            self.status.set("沒有輸出")
            self.percent.set("")
            self._log(f"沒有輸出：{message}", "error")
            self._update_controls()
            if not result.blocked:
                messagebox.showerror(TITLE, message, parent=self.root)
            elif messagebox.askyesno(
                TITLE,
                message + "\n\n要打開匯出 cookies 的教學嗎？",
                icon="error",
                parent=self.root,
            ):
                self._show_tutorial()
            return
        assert result.output is not None
        self.last_output = result.output
        self.progress.configure(value=self.progress.cget("maximum"))
        self.percent.set("100%")
        self.status.set(f"完成：{result.output.name}")
        self._log(f"完成：{result.output}", "success")
        self._update_controls()
        if not result.failures:
            messagebox.showinfo(TITLE, f"完成！\n{result.output}", parent=self.root)
            return
        lines = [f"第 {f.position} 段  {f.youtube_id}  {f.reason}" for f in result.failures]
        self._log(f"有 {len(result.failures)} 個片段下載失敗，這些段落改成靜態畫面：", "error")
        for line in lines:
            self._log(f"  {line}", "error")
        summary = (
            f"影片輸出了，但有 {len(result.failures)} 個片段下載失敗，這些段落改成靜態畫面：\n\n"
            + "\n".join(lines)
            + "\n\n可以回 CRITShowCase 頁面換掉這些片段，重新匯出後再出一次。"
        )
        if result.update_hint:
            self._log(result.update_hint)
            if messagebox.askyesno(TITLE, f"{summary}\n\n{result.update_hint}\n\n要打開下載頁面嗎？", icon="warning", parent=self.root):
                webbrowser.open(RELEASES)
            return
        messagebox.showwarning(TITLE, summary, parent=self.root)

    # ---- 其他 ----

    def _log(self, line: str, tag: str | None = None) -> None:
        """tag："error" 或 "success"，換顏色。"""
        self.log.configure(state="normal")
        self.log.insert("end", f"{datetime.now():%H:%M:%S}  ", "time")
        self.log.insert("end", line + "\n", tag or ())
        self.log.see("end")
        self.log.configure(state="disabled")

    def _copy_log(self) -> None:
        self.root.clipboard_clear()
        self.root.clipboard_append(self.log.get("1.0", "end-1c"))

    def _open_folder(self) -> None:
        if self.last_output is None:
            return
        if sys.platform == "win32":
            subprocess.Popen(["explorer", "/select,", str(self.last_output)])
        elif sys.platform == "darwin":
            subprocess.Popen(["open", "-R", str(self.last_output)])
        else:
            subprocess.Popen(["xdg-open", str(self.last_output.parent)])

    def _report_error(self, kind: type[BaseException], error: BaseException, traceback: TracebackType | None) -> None:
        """按鈕的處理出錯時（例如匯入 cookies 時資料夾沒有寫入權限）：Tk 預設印到 stderr，打包版的 GUI 看不到。"""
        self._log(f"發生錯誤：{error!r}", "error")
        messagebox.showerror(TITLE, f"發生錯誤：{error}", parent=self.root)

    def _close(self) -> None:
        if self.worker is not None and not messagebox.askyesno(
            TITLE,
            "影片還沒輸出完成，確定要關閉嗎？\n已經下載好的片段會留在快取，下次不必重新下載。",
            icon="warning",
            parent=self.root,
        ):
            return
        self.root.destroy()

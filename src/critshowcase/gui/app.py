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
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from critshowcase import package_version
from critshowcase.download import RELEASES
from critshowcase.job import JobResult, default_output, run_job
from critshowcase.render import Progress

TITLE = "CRITShowCase 出片工具"
POLL_MS = 100
DOTS_MS = 500
PAD = 8


class App:
    def __init__(self, root: tk.Tk, source: Path | None = None) -> None:
        self.root = root
        self.events: queue.Queue[Progress | JobResult] = queue.Queue()
        self.worker: threading.Thread | None = None
        self.last_output: Path | None = None
        self.joining = False
        self.source = tk.StringVar()
        self.output = tk.StringVar()
        self.refresh = tk.BooleanVar()
        self.status = tk.StringVar(value="選擇網頁匯出的影片專案後，按「開始出片」。")
        root.title(TITLE)
        root.minsize(600, 520)
        root.protocol("WM_DELETE_WINDOW", self._close)
        self._build()
        if source:
            self._set_source(Path(source))
        self._update_controls()

    # ---- 版面 ----

    def _build(self) -> None:
        frame = ttk.Frame(self.root, padding=PAD * 2)
        frame.grid(sticky="nsew")
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        frame.columnconfigure(0, weight=1)

        project = ttk.LabelFrame(frame, text="影片專案（網頁匯出的 zip 或 project.json）", padding=PAD)
        project.grid(row=0, column=0, sticky="ew")
        project.columnconfigure(0, weight=1)
        ttk.Entry(project, textvariable=self.source, state="readonly").grid(row=0, column=0, sticky="ew")
        self.choose_source = ttk.Button(project, text="選擇…", command=self._choose_source)
        self.choose_source.grid(row=0, column=1, padx=(PAD, 0))

        output = ttk.LabelFrame(frame, text="輸出 mp4", padding=PAD)
        output.grid(row=1, column=0, sticky="ew", pady=(PAD, 0))
        output.columnconfigure(0, weight=1)
        ttk.Entry(output, textvariable=self.output, state="readonly").grid(row=0, column=0, sticky="ew")
        self.choose_output = ttk.Button(output, text="另存為…", command=self._choose_output)
        self.choose_output.grid(row=0, column=1, padx=(PAD, 0))

        self.refresh_box = ttk.Checkbutton(frame, text="不用快取，所有片段重新下載", variable=self.refresh)
        self.refresh_box.grid(row=3, column=0, sticky="w", pady=(PAD, 0))

        self.start = ttk.Button(frame, text="開始出片", command=self._start)
        self.start.grid(row=4, column=0, sticky="ew", pady=(PAD, 0), ipady=4)

        self.progress = ttk.Progressbar(frame, mode="determinate", maximum=1)
        self.progress.grid(row=5, column=0, sticky="ew", pady=(PAD * 2, 0))
        ttk.Label(frame, textvariable=self.status).grid(row=6, column=0, sticky="w", pady=(4, 0))

        log = ttk.Frame(frame)
        log.grid(row=7, column=0, sticky="nsew", pady=(PAD, 0))
        frame.rowconfigure(7, weight=1)
        log.columnconfigure(0, weight=1)
        log.rowconfigure(0, weight=1)
        self.log = tk.Text(log, height=10, wrap="word", state="disabled")
        self.log.grid(row=0, column=0, sticky="nsew")
        scrollbar = ttk.Scrollbar(log, orient="vertical", command=self.log.yview)
        scrollbar.grid(row=0, column=1, sticky="ns")
        self.log.configure(yscrollcommand=scrollbar.set)

        bottom = ttk.Frame(frame)
        bottom.grid(row=8, column=0, sticky="ew", pady=(PAD, 0))
        bottom.columnconfigure(0, weight=1)
        versions = f"critshowcase {package_version('critshowcase')}　yt-dlp {package_version('yt-dlp')}"
        ttk.Label(bottom, text=versions, foreground="gray").grid(row=0, column=0, sticky="w")
        ttk.Button(bottom, text="複製紀錄", command=self._copy_log).grid(row=0, column=1, padx=(PAD, 0))
        self.open_folder = ttk.Button(bottom, text="開啟資料夾", command=self._open_folder)
        self.open_folder.grid(row=0, column=2, padx=(PAD, 0))

    def _update_controls(self) -> None:
        busy = self.worker is not None
        idle = "disabled" if busy else "normal"
        for widget in (self.choose_source, self.choose_output, self.refresh_box):
            widget.configure(state=idle)
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

    # ---- 出片 ----

    def _start(self) -> None:
        source, output = Path(self.source.get()), Path(self.output.get())
        self.last_output = None
        self.progress.configure(value=0, maximum=1)
        self._log(f"開始出片：{source}")
        self.status.set("準備中…")
        self.worker = threading.Thread(target=self._work, args=(source, output, self.refresh.get()), daemon=True)
        self.worker.start()
        self._update_controls()
        self.root.after(POLL_MS, self._poll)

    def _work(self, source: Path, output: Path, refresh: bool) -> None:
        """背景執行緒：不碰任何 widget。"""
        try:
            result = run_job(source, output, refresh=refresh, progress=self.events.put)
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
        if event.stage == "done":
            return
        self.status.set(event.message)
        self._log(event.message)
        # 輸出 mp4 只有一步但可能很久：不假裝知道百分比，讓狀態文字動著，看得出還在跑
        if event.stage == "join" and not self.joining:
            self.joining = True
            self._animate_dots(0)

    def _animate_dots(self, count: int) -> None:
        if not self.joining:
            return
        self.status.set("輸出 mp4" + "." * (count % 4))
        self.root.after(DOTS_MS, self._animate_dots, count + 1)

    def _finish(self, result: JobResult) -> None:
        self.worker = None
        self.joining = False
        if result.error is not None:
            self.status.set("沒有輸出")
            self._log(f"沒有輸出：{result.error}")
            self._update_controls()
            messagebox.showerror(TITLE, result.error, parent=self.root)
            return
        assert result.output is not None
        self.last_output = result.output
        self.progress.configure(value=self.progress.cget("maximum"))
        self.status.set(f"完成：{result.output}")
        self._log(f"完成：{result.output}")
        self._update_controls()
        if not result.failures:
            messagebox.showinfo(TITLE, f"完成！\n{result.output}", parent=self.root)
            return
        lines = [f"第 {f.position} 段  {f.youtube_id}  {f.reason}" for f in result.failures]
        self._log(f"有 {len(result.failures)} 個片段下載失敗，這些段落改成靜態畫面：")
        for line in lines:
            self._log(f"  {line}")
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

    def _log(self, line: str) -> None:
        self.log.configure(state="normal")
        self.log.insert("end", line + "\n")
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

    def _close(self) -> None:
        if self.worker is not None and not messagebox.askyesno(
            TITLE,
            "影片還沒輸出完成，確定要關閉嗎？\n已經下載好的片段會留在快取，下次不必重新下載。",
            icon="warning",
            parent=self.root,
        ):
            return
        self.root.destroy()

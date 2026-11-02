"""中文 GUI：视频码率计算器。Python 3.10+，运行时不依赖第三方包。"""
from __future__ import annotations

import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from pathlib import Path

from bitrate_core import (
    CODECS, PROFILES, calculate, detect_duration, format_duration,
    make_preset, recommend,
)

BG = "#f4f6fa"
WHITE = "#ffffff"
NAVY = "#17324d"
BLUE = "#2563eb"
MUTED = "#66788a"


class VideoBitrateCalculator(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("视频码率计算器 · 180 MB 上传助手")
        self.geometry("1030x880")
        self.minsize(860, 780)
        self.configure(background=BG)
        self.vars = {
            "duration": tk.StringVar(value="9:38"),
            "limit": tk.StringVar(value="180"),
            "target": tk.StringVar(value="170"),
            "audio": tk.StringVar(value="128"),
            "overhead": tk.StringVar(value="1.5"),
            "profile": tk.StringVar(value="综合（一般游戏）"),
        }
        self.current = None
        self.selected_codec = "AV1"
        self.file_path = ""
        self.after_job = None
        self._setup_style()
        self._build()
        for v in self.vars.values():
            v.trace_add("write", self._debounce)
        self.recalculate()

    def _setup_style(self):
        self.option_add("*Font", "{Segoe UI} 10")
        style = ttk.Style(self)
        if "clam" in style.theme_names():
            style.theme_use("clam")
        style.configure("TFrame", background=BG)
        style.configure("Card.TFrame", background=WHITE)
        style.configure("TLabel", background=BG, foreground=NAVY, font=("Segoe UI", 10))
        style.configure("Card.TLabel", background=WHITE, foreground=NAVY)
        style.configure("Muted.TLabel", background=BG, foreground=MUTED)
        style.configure("CardMuted.TLabel", background=WHITE, foreground=MUTED)
        style.configure("Title.TLabel", background=BG, foreground=NAVY, font=("Segoe UI Semibold", 21))
        style.configure("Section.TLabel", background=WHITE, foreground=NAVY, font=("Segoe UI Semibold", 12))
        style.configure("Big.TLabel", background=WHITE, foreground=BLUE, font=("Segoe UI Semibold", 26))
        style.configure("TEntry", padding=5)
        style.configure("TCombobox", padding=4)
        style.configure("Treeview", rowheight=29, font=("Segoe UI", 10), background=WHITE, fieldbackground=WHITE)
        style.configure("Treeview.Heading", font=("Segoe UI Semibold", 10), background="#e8effa", foreground=NAVY)
        style.map("Treeview", background=[("selected", "#dce9ff")], foreground=[("selected", NAVY)])
        style.configure("Accent.TButton", padding=(13, 8), background=BLUE, foreground=WHITE, font=("Segoe UI Semibold", 10))
        style.map("Accent.TButton", background=[("active", "#1748b6")])
        style.configure("Soft.TButton", padding=(11, 8), background="#e8effa", foreground=NAVY)
        style.map("Soft.TButton", background=[("active", "#d6e4fa")])

    def _build(self):
        outer = ttk.Frame(self, padding=(22, 18, 22, 14))
        outer.pack(fill="both", expand=True)
        ttk.Label(outer, text="视频码率计算器", style="Title.TLabel").pack(anchor="w")
        ttk.Label(outer, text="录制时长不固定？选择原片或输入时长，即可计算 180 MB 等上传限制下的平均码率。", style="Muted.TLabel").pack(anchor="w", pady=(2, 14))

        first = ttk.Frame(outer, style="Card.TFrame", padding=15)
        first.pack(fill="x")
        ttk.Label(first, text="① 原片和上传限制", style="Section.TLabel").pack(anchor="w", pady=(0, 10))
        file_row = ttk.Frame(first, style="Card.TFrame")
        file_row.pack(fill="x", pady=(0, 10))
        ttk.Button(file_row, text="选择原片，自动读取时长", style="Accent.TButton", command=self.choose_file).pack(side="left")
        self.file_label = ttk.Label(file_row, text="未选择文件；可直接手动输入时长", style="CardMuted.TLabel")
        self.file_label.pack(side="left", padx=(12, 0))

        fields = ttk.Frame(first, style="Card.TFrame")
        fields.pack(fill="x")
        specs = [
            ("duration", "时长 (分:秒)", 17),
            ("limit", "网站上限 (MB)", 15),
            ("target", "目标体积 (MB)", 15),
            ("audio", "音频 (Kbps)", 14),
            ("overhead", "封装余量 (%)", 15),
        ]
        for col, (key, label, width) in enumerate(specs):
            box = ttk.Frame(fields, style="Card.TFrame")
            box.grid(row=0, column=col, padx=(0, 10 if col < 4 else 0), sticky="ew")
            fields.columnconfigure(col, weight=1)
            ttk.Label(box, text=label, style="CardMuted.TLabel").pack(anchor="w", pady=(0, 4))
            ttk.Entry(box, textvariable=self.vars[key], width=width).pack(fill="x")
        profile_row = ttk.Frame(first, style="Card.TFrame")
        profile_row.pack(fill="x", pady=(10, 0))
        ttk.Label(profile_row, text="内容类型 / 清晰度参考：", style="Card.TLabel").pack(side="left")
        ttk.Combobox(profile_row, textvariable=self.vars["profile"], values=list(PROFILES), width=23,
                     state="readonly").pack(side="left", padx=5)
        ttk.Label(profile_row, text="采用十进制 MB；音频有多音轨时请填码率总和。", style="CardMuted.TLabel").pack(side="left", padx=12)

        metrics = ttk.Frame(outer, style="Card.TFrame", padding=(17, 12))
        metrics.pack(fill="x", pady=(12, 12))
        metrics.columnconfigure(0, weight=1)
        metrics.columnconfigure(1, weight=1)
        metrics.columnconfigure(2, weight=1)
        m0 = ttk.Frame(metrics, style="Card.TFrame")
        m0.grid(row=0, column=0, sticky="w")
        ttk.Label(m0, text="可用视频平均码率", style="CardMuted.TLabel").pack(anchor="w")
        self.bitrate_label = ttk.Label(m0, text="—", style="Big.TLabel")
        self.bitrate_label.pack(anchor="w")
        m1 = ttk.Frame(metrics, style="Card.TFrame")
        m1.grid(row=0, column=1, sticky="w")
        ttk.Label(m1, text="文件大小估计", style="CardMuted.TLabel").pack(anchor="w")
        self.size_label = ttk.Label(m1, text="—", style="Section.TLabel")
        self.size_label.pack(anchor="w", pady=(10, 0))
        m2 = ttk.Frame(metrics, style="Card.TFrame")
        m2.grid(row=0, column=2, sticky="w")
        ttk.Label(m2, text="当前时长", style="CardMuted.TLabel").pack(anchor="w")
        self.duration_label = ttk.Label(m2, text="—", style="Section.TLabel")
        self.duration_label.pack(anchor="w", pady=(10, 0))
        self.status_label = ttk.Label(outer, text="", style="Muted.TLabel")
        self.status_label.pack(anchor="w", pady=(0, 9))

        actions = ttk.Frame(outer)
        actions.pack(side="bottom", fill="x", pady=(12, 0))
        ttk.Button(actions, text="复制码率", style="Accent.TButton", command=self.copy_bitrate).pack(side="left", padx=(0, 8))
        ttk.Button(actions, text="复制所选格式完整参数", style="Soft.TButton", command=self.copy_selected).pack(side="left", padx=(0, 8))
        ttk.Button(actions, text="复制全部四种编码参数", style="Soft.TButton", command=self.copy_all).pack(side="left", padx=(0, 8))
        ttk.Button(actions, text="导出 TXT", style="Soft.TButton", command=self.export_txt).pack(side="left")
        ttk.Label(outer, text="注意：码率预算和分辨率建议不保证最终文件一定小于上限，也不保证肉眼无损；上传前请检查文件大小与运动场景。", style="Muted.TLabel").pack(side="bottom", anchor="w", pady=(11, 0))


        mid = ttk.Frame(outer, style="Card.TFrame", padding=13)
        mid.pack(fill="both", expand=True)
        ttk.Label(mid, text="② 编码方式比较（点击查看每种格式的完整参数）", style="Section.TLabel").pack(anchor="w", pady=(0, 8))
        ttk.Label(mid, text="同一时长与文件大小限制下，码率预算基本相同；不同编码格式的压缩效率与兼容性不同。", style="CardMuted.TLabel").pack(anchor="w", pady=(0, 8))
        gridbox = ttk.Frame(mid, style="Card.TFrame")
        gridbox.pack(fill="x")
        columns = ("codec", "rate", "encoder", "advice")
        self.table = ttk.Treeview(gridbox, columns=columns, show="headings", height=4, selectmode="browse")
        for name, title, width in [
            ("codec", "编码格式", 150), ("rate", "平均码率", 120),
            ("encoder", "HandBrake 编码器", 230), ("advice", "建议画面", 245),
        ]:
            self.table.heading(name, text=title)
            self.table.column(name, width=width, minwidth=110, stretch=(name in {"encoder", "advice"}))
        self.table.pack(fill="x")
        self.table.bind("<<TreeviewSelect>>", self.on_select)
        self.preview_label = ttk.Label(mid, text="③ 当前所选格式的完整 HandBrake 参数", style="Section.TLabel")
        self.preview_label.pack(anchor="w", pady=(14, 6))
        textframe = ttk.Frame(mid, style="Card.TFrame")
        textframe.pack(fill="both", expand=True)
        self.preview = tk.Text(textframe, height=5, font=("Consolas", 10), wrap="word", bg="#f7f9fc",
                               fg=NAVY, insertbackground=NAVY, relief="flat", padx=12, pady=8)
        self.preview.pack(side="left", fill="both", expand=True)
        sc = ttk.Scrollbar(textframe, orient="vertical", command=self.preview.yview)
        sc.pack(side="right", fill="y")
        self.preview.configure(yscrollcommand=sc.set, state="disabled")

    def _debounce(self, *_):
        if self.after_job is not None:
            self.after_cancel(self.after_job)
        self.after_job = self.after(180, self.recalculate)

    def choose_file(self):
        name = filedialog.askopenfilename(
            title="选择要压缩的视频原片",
            filetypes=[("视频文件", "*.mp4 *.m4v *.mov *.mkv *.webm *.avi *.ts *.m2ts *.flv"), ("所有文件", "*.*")],
        )
        if not name:
            return
        self.file_path = name
        self.file_label.config(text=f"正在读取：{Path(name).name[:58]}")
        self.update_idletasks()
        seconds, method = detect_duration(name)
        if seconds:
            self.vars["duration"].set(format_duration(seconds))
            self.file_label.config(text=f"{Path(name).name[:42]}  ·  已识别时长（{method}）")
        else:
            self.file_label.config(text=f"{Path(name).name[:40]}  ·  {method}")
            messagebox.showinfo("需要手动填写时长", "此格式/文件无法自动解析时长。\n\n可以手动填写，也可以将 ffprobe.exe 放在程序同目录，或放入打包文件夹后重建 EXE。")

    def recalculate(self):
        self.after_job = None
        try:
            b = calculate(self.vars["duration"].get(), self.vars["limit"].get(),
                          self.vars["target"].get(), self.vars["audio"].get(),
                          self.vars["overhead"].get())
        except ValueError as exc:
            self.current = None
            self.bitrate_label.config(text="—")
            self.size_label.config(text="—")
            self.duration_label.config(text="—")
            self.status_label.config(text=f"需要调整输入：{exc}")
            self._draw_rows()
            return
        self.current = b
        self.bitrate_label.config(text=f"{b.video_kbps:,} Kbps")
        self.size_label.config(text=f"约 {b.estimated_mb:.1f} MB")
        self.duration_label.config(text=format_duration(b.seconds))
        self.status_label.config(text=f"上限 {b.limit_mb:g} MB · 安全余量 {b.limit_mb - b.target_mb:g} MB · 已为封装预留 {b.overhead_pct:g}%")
        self._draw_rows()

    def _draw_rows(self):
        for child in self.table.get_children():
            self.table.delete(child)
        if self.current:
            for codec, meta in CODECS.items():
                advice, _ = recommend(codec, self.current.video_kbps, self.vars["profile"].get())
                self.table.insert("", "end", iid=codec, values=(codec, f"{self.current.video_kbps:,} Kbps", meta["encoder"], advice))
            if self.selected_codec not in CODECS:
                self.selected_codec = "AV1"
            self.table.selection_set(self.selected_codec)
            self.table.focus(self.selected_codec)
        self.refresh_preview()

    def on_select(self, _):
        rows = self.table.selection()
        if rows and rows[0] in CODECS:
            self.selected_codec = rows[0]
            self.refresh_preview()

    def refresh_preview(self):
        self.preview.configure(state="normal")
        self.preview.delete("1.0", "end")
        if self.current:
            self.preview.insert("1.0", make_preset(self.selected_codec, self.current, self.vars["profile"].get()))
        else:
            self.preview.insert("1.0", "填写有效的视频时长、文件大小和音频码率后，将显示完整参数。")
        self.preview.configure(state="disabled")

    def _copy(self, value: str):
        self.clipboard_clear()
        self.clipboard_append(value)
        self.update()
        self.status_label.config(text="已复制到剪贴板。")

    def copy_bitrate(self):
        if self._valid():
            self._copy(str(self.current.video_kbps))

    def copy_selected(self):
        if self._valid():
            self._copy(make_preset(self.selected_codec, self.current, self.vars["profile"].get()))

    def all_presets(self) -> str:
        b = self.current
        return ("\n\n" + "=" * 60 + "\n\n").join(
            make_preset(name, b, self.vars["profile"].get()) for name in CODECS
        )

    def copy_all(self):
        if self._valid():
            self._copy(self.all_presets())

    def export_txt(self):
        if not self._valid():
            return
        path = filedialog.asksaveasfilename(defaultextension=".txt", initialfile="视频上传码率与编码参数.txt",
                                            filetypes=[("文本文件", "*.txt")])
        if not path:
            return
        try:
            Path(path).write_text(self.all_presets(), encoding="utf-8-sig")
        except OSError as exc:
            messagebox.showerror("保存失败", str(exc))
        else:
            self.status_label.config(text=f"已导出：{path}")

    def _valid(self) -> bool:
        if self.current is None:
            messagebox.showwarning("无法计算", "请先修正输入项。")
            return False
        return True


if __name__ == "__main__":
    VideoBitrateCalculator().mainloop()

"""Turkish Tkinter GUI: TV connection, source, subtitle region, start/stop."""

from __future__ import annotations

import queue
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from . import winapi
from .capture import CaptureError, open_source, suggest_window
from .config import Config
from .pipeline import Pipeline
from .receiver import ReceiverError, TvReceiver
from .translate import Translator

DEFAULT_REGION = [0.10, 0.72, 0.80, 0.25]
SOURCES = [
    ("window", "PS Remote Play / chiaki-ng penceresi"),
    ("card", "Yakalama kartı (capture card)"),
    ("screen", "Tüm ekran"),
    ("file", "Kayıttan test (resim klasörü / video)"),
]
METHODS = [
    ("auto", "Otomatik (önerilen)"),
    ("printwindow", "Arkada kalsa da yakala"),
    ("screen", "Ekrandan kopyala (pencere görünür olmalı)"),
]


class RegionPicker(tk.Toplevel):
    """Shows one captured frame; drag a rectangle over the subtitle area."""

    MAX_W, MAX_H = 960, 540

    def __init__(self, master, frame, region, on_done):
        super().__init__(master)
        from PIL import Image, ImageTk

        self.title("Altyazı bölgesini seçin — fareyle sürükleyin")
        self.on_done = on_done
        img = Image.fromarray(frame)
        scale = min(self.MAX_W / img.width, self.MAX_H / img.height, 1.0)
        self.w, self.h = int(img.width * scale), int(img.height * scale)
        self.photo = ImageTk.PhotoImage(img.resize((self.w, self.h)))
        self.canvas = tk.Canvas(self, width=self.w, height=self.h, highlightthickness=0, cursor="crosshair")
        self.canvas.pack()
        self.canvas.create_image(0, 0, anchor="nw", image=self.photo)
        x, y, rw, rh = region
        self.rect = self.canvas.create_rectangle(
            x * self.w, y * self.h, (x + rw) * self.w, (y + rh) * self.h, outline="#00e676", width=3
        )
        self.start = (0, 0)
        self.canvas.bind("<ButtonPress-1>", self._press)
        self.canvas.bind("<B1-Motion>", self._drag)
        bar = ttk.Frame(self, padding=6)
        bar.pack(fill="x")
        ttk.Label(bar, text="Yeşil kutu İngilizce altyazının çıktığı alanı kapsamalı (harita ve para göstergesi dışarıda).").pack(side="left")
        ttk.Button(bar, text="Kaydet", command=self._save).pack(side="right")
        ttk.Button(bar, text="Varsayılan", command=self._default).pack(side="right", padx=4)
        self.grab_set()

    def _press(self, e):
        self.start = (e.x, e.y)
        self.canvas.coords(self.rect, e.x, e.y, e.x, e.y)

    def _drag(self, e):
        x0, y0 = self.start
        self.canvas.coords(self.rect, x0, y0, min(max(e.x, 0), self.w), min(max(e.y, 0), self.h))

    def _default(self):
        x, y, rw, rh = DEFAULT_REGION
        self.canvas.coords(self.rect, x * self.w, y * self.h, (x + rw) * self.w, (y + rh) * self.h)

    def _save(self):
        x0, y0, x1, y1 = self.canvas.coords(self.rect)
        x0, x1 = sorted((x0, x1))
        y0, y1 = sorted((y0, y1))
        if x1 - x0 < 20 or y1 - y0 < 10:
            messagebox.showwarning("Bölge", "Bölge çok küçük, tekrar sürükleyin.", parent=self)
            return
        self.on_done([round(x0 / self.w, 4), round(y0 / self.h, 4), round((x1 - x0) / self.w, 4), round((y1 - y0) / self.h, 4)])
        self.destroy()


class Preview(tk.Toplevel):
    def __init__(self, master):
        super().__init__(master)
        self.title("Türkçe altyazı önizleme")
        self.configure(bg="black")
        self.attributes("-topmost", True)
        self.geometry("1000x140+100+40")
        self.label = tk.Label(self, text="…", fg="white", bg="black", font=("Segoe UI", 24, "bold"), wraplength=960, justify="center")
        self.label.pack(expand=True, fill="both", padx=10, pady=10)

    def show(self, text: str):
        self.label.configure(text=text)


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.cfg = Config.load()
        self.title("PS5 Altyazı Çevirmeni (İngilizce → Türkçe)")
        self.minsize(640, 600)
        self.events: queue.Queue = queue.Queue()
        self.pipeline: Pipeline | None = None
        self.preview: Preview | None = None
        self._ocr = None
        self._build()
        self.after(100, self._poll)
        self.protocol("WM_DELETE_WINDOW", self._close)
        if self.cfg.source_kind == "window":
            self._refresh_windows()

    # ---- layout -------------------------------------------------------------------------
    def _build(self):
        pad = {"padx": 8, "pady": 4}
        root = ttk.Frame(self, padding=10)
        root.pack(fill="both", expand=True)

        tv = ttk.LabelFrame(root, text="1) TV bağlantısı (TV'de: Ekran çevirisi → Ağ alıcısını aç)", padding=8)
        tv.pack(fill="x", **pad)
        ttk.Label(tv, text="TV IP adresi:").grid(row=0, column=0, sticky="w")
        self.tv_var = tk.StringVar(value=self.cfg.tv_address)
        ttk.Entry(tv, textvariable=self.tv_var, width=24).grid(row=0, column=1, sticky="w", padx=4)
        ttk.Label(tv, text="Eşleştirme kodu:").grid(row=0, column=2, sticky="w", padx=(12, 0))
        self.token_var = tk.StringVar(value=self.cfg.token)
        ttk.Entry(tv, textvariable=self.token_var, width=12).grid(row=0, column=3, sticky="w", padx=4)
        ttk.Button(tv, text="Bağlantıyı dene", command=self._test_tv).grid(row=0, column=4, padx=6)
        self.tv_result = ttk.Label(tv, text="", foreground="#555")
        self.tv_result.grid(row=1, column=0, columnspan=5, sticky="w", pady=(4, 0))

        src = ttk.LabelFrame(root, text="2) Görüntü kaynağı", padding=8)
        src.pack(fill="x", **pad)
        self.kind_var = tk.StringVar(value=self.cfg.source_kind)
        for i, (key, label) in enumerate(SOURCES):
            ttk.Radiobutton(src, text=label, value=key, variable=self.kind_var, command=self._kind_changed).grid(
                row=i // 2, column=i % 2, sticky="w"
            )
        self.value_var = tk.StringVar(value=self.cfg.source_value)
        row = ttk.Frame(src)
        row.grid(row=2, column=0, columnspan=2, sticky="we", pady=(6, 0))
        self.value_label = ttk.Label(row, text="Pencere:")
        self.value_label.pack(side="left")
        self.value_box = ttk.Combobox(row, textvariable=self.value_var, width=48)
        self.value_box.pack(side="left", padx=4, fill="x", expand=True)
        self.value_btn = ttk.Button(row, text="Yenile", command=self._value_button)
        self.value_btn.pack(side="left")
        mrow = ttk.Frame(src)
        mrow.grid(row=3, column=0, columnspan=2, sticky="w", pady=(4, 0))
        ttk.Label(mrow, text="Yakalama yöntemi:").pack(side="left")
        self.method_var = tk.StringVar(value=dict(METHODS).get(self.cfg.capture_method, METHODS[0][1]))
        ttk.Combobox(mrow, textvariable=self.method_var, values=[m[1] for m in METHODS], state="readonly", width=40).pack(
            side="left", padx=4
        )

        reg = ttk.LabelFrame(root, text="3) Altyazı bölgesi ve seçenekler", padding=8)
        reg.pack(fill="x", **pad)
        self.region_label = ttk.Label(reg, text=self._region_text())
        self.region_label.grid(row=0, column=0, sticky="w")
        ttk.Button(reg, text="Bölgeyi ayarla…", command=self._pick_region).grid(row=0, column=1, padx=6)
        self.send_var = tk.BooleanVar(value=self.cfg.send_to_tv)
        self.preview_var = tk.BooleanVar(value=self.cfg.preview)
        self.place_var = tk.StringVar(value=self.cfg.placement)
        ttk.Checkbutton(reg, text="TV'ye gönder", variable=self.send_var).grid(row=1, column=0, sticky="w")
        ttk.Checkbutton(reg, text="PC'de önizleme penceresi", variable=self.preview_var).grid(row=1, column=1, sticky="w")
        ttk.Radiobutton(reg, text="Türkçeyi İngilizcenin üstüne yaz", value="over", variable=self.place_var).grid(row=2, column=0, sticky="w")
        ttk.Radiobutton(reg, text="Ekranın en altına yaz", value="bottom", variable=self.place_var).grid(row=2, column=1, sticky="w")

        run = ttk.Frame(root)
        run.pack(fill="x", **pad)
        self.start_btn = ttk.Button(run, text="▶  BAŞLAT", command=self._toggle)
        self.start_btn.pack(side="left", ipadx=20, ipady=8)
        self.status = ttk.Label(run, text="Hazır.", foreground="#555")
        self.status.pack(side="left", padx=12)

        out = ttk.LabelFrame(root, text="Son altyazı", padding=8)
        out.pack(fill="both", expand=True, **pad)
        self.en_label = ttk.Label(out, text="EN: —", wraplength=600, foreground="#666")
        self.en_label.pack(anchor="w")
        self.tr_label = ttk.Label(out, text="TR: —", wraplength=600, font=("Segoe UI", 13, "bold"))
        self.tr_label.pack(anchor="w", pady=(2, 6))
        self.log = tk.Text(out, height=7, state="disabled", wrap="word", font=("Consolas", 9))
        self.log.pack(fill="both", expand=True)
        self._kind_changed()

    def _region_text(self):
        x, y, w, h = self.cfg.region
        return f"Bölge: soldan %{x*100:.0f}, üstten %{y*100:.0f}, genişlik %{w*100:.0f}, yükseklik %{h*100:.0f}"

    def _kind_changed(self):
        kind = self.kind_var.get()
        labels = {"window": ("Pencere:", "Yenile"), "card": ("Kart no:", "—"), "screen": ("Ekran no:", "—"), "file": ("Yol:", "Seç…")}
        text, btn = labels[kind]
        self.value_label.configure(text=text)
        self.value_btn.configure(text=btn, state="disabled" if btn == "—" else "normal")
        if kind == "window":
            self._refresh_windows()
            return
        self.value_box.configure(values=[])
        if kind in ("card", "screen") and not self.value_var.get().isdigit():
            self.value_var.set("0" if kind == "card" else "1")

    def _value_button(self):
        if self.kind_var.get() == "window":
            self._refresh_windows()
        elif self.kind_var.get() == "file":
            path = filedialog.askopenfilename(
                title="Video ya da resim seçin", filetypes=[("Video/resim", "*.mp4 *.mkv *.avi *.mov *.webm *.png *.jpg"), ("Hepsi", "*.*")]
            )
            if path:
                self.value_var.set(path)

    def _refresh_windows(self):
        titles = [t for _, t in winapi.list_windows() if t.strip() and t != self.title()]
        self.value_box.configure(values=titles)
        suggested = suggest_window()
        if suggested and (not self.value_var.get() or self.value_var.get() not in titles):
            self.value_var.set(suggested)

    # ---- actions ------------------------------------------------------------------------
    def _collect(self) -> Config:
        cfg = self.cfg
        cfg.tv_address = self.tv_var.get().strip()
        cfg.token = self.token_var.get().strip()
        cfg.source_kind = self.kind_var.get()
        cfg.source_value = self.value_var.get().strip()
        cfg.capture_method = {label: key for key, label in METHODS}.get(self.method_var.get(), "auto")
        cfg.send_to_tv = self.send_var.get()
        cfg.preview = self.preview_var.get()
        cfg.placement = self.place_var.get()
        try:
            cfg.save()
        except OSError:
            pass
        return cfg

    def _test_tv(self):
        cfg = self._collect()
        self.tv_result.configure(text="Deneniyor…", foreground="#555")

        def work():
            try:
                msg, ok = TvReceiver(cfg.tv_address, cfg.token).test(), True
            except ReceiverError as e:
                msg, ok = str(e), False
            self.events.put(("tv_test", {"message": msg, "ok": ok}))

        threading.Thread(target=work, daemon=True).start()

    def _pick_region(self):
        cfg = self._collect()
        try:
            source = open_source(cfg.source_kind, cfg.source_value, cfg.capture_method)
            frame = source.grab()
            source.close()
        except CaptureError as e:
            messagebox.showerror("Görüntü alınamadı", str(e))
            return
        if frame is None:
            messagebox.showerror("Görüntü alınamadı", "Kaynaktan görüntü gelmedi.")
            return

        def done(region):
            self.cfg.region = region
            self.region_label.configure(text=self._region_text())
            self._collect()

        RegionPicker(self, frame, cfg.region, done)

    def _toggle(self):
        if self.pipeline:
            self.pipeline.stop()
            self.start_btn.configure(state="disabled")
            return
        cfg = self._collect()
        if cfg.send_to_tv and (not cfg.tv_address or not cfg.token):
            messagebox.showwarning("TV", "TV IP adresini ve eşleştirme kodunu girin (ya da 'TV'ye gönder'i kapatın).")
            return
        self.start_btn.configure(state="disabled")
        self.status.configure(text="Başlatılıyor (OCR modeli yükleniyor)…")

        def work():
            try:
                if self._ocr is None:
                    from .ocr import OcrEngine

                    self._ocr = OcrEngine()
                source = open_source(cfg.source_kind, cfg.source_value, cfg.capture_method)
                receiver = TvReceiver(cfg.tv_address, cfg.token) if cfg.send_to_tv else None
                pipeline = Pipeline(cfg, source, self._ocr, Translator(server_url=cfg.server_url), receiver,
                                    lambda kind, data: self.events.put((kind, data)))
                self.events.put(("started", {"pipeline": pipeline}))
            except Exception as e:
                self.events.put(("start_failed", {"message": str(e)}))

        threading.Thread(target=work, daemon=True).start()

    def _log(self, text: str):
        self.log.configure(state="normal")
        self.log.insert("end", text + "\n")
        self.log.see("end")
        self.log.configure(state="disabled")

    def _poll(self):
        try:
            while True:
                kind, data = self.events.get_nowait()
                self._handle(kind, data)
        except queue.Empty:
            pass
        self.after(100, self._poll)

    def _handle(self, kind: str, data: dict):
        if kind == "tv_test":
            self.tv_result.configure(text=data["message"], foreground="#1b7f2a" if data["ok"] else "#b00020")
        elif kind == "started":
            self.pipeline = data["pipeline"]
            self.pipeline.start()
            self.start_btn.configure(text="■  DURDUR", state="normal")
            if self.cfg.preview and not (self.preview and self.preview.winfo_exists()):
                self.preview = Preview(self)
        elif kind == "start_failed":
            self.start_btn.configure(state="normal")
            self.status.configure(text="Başlatılamadı.")
            messagebox.showerror("Başlatılamadı", data["message"])
        elif kind == "status":
            self.status.configure(text=data["message"])
        elif kind == "subtitle":
            self.en_label.configure(text="EN: " + data["english"])
            self.tr_label.configure(text="TR: " + data["turkish"])
            self._log(f"→ {data['turkish']}")
            if self.preview and self.preview.winfo_exists():
                self.preview.show(data["turkish"])
        elif kind == "clear":
            if self.preview and self.preview.winfo_exists():
                self.preview.show("")
        elif kind == "error":
            self._log("! " + data["message"])
        elif kind == "stopped":
            self.pipeline = None
            self.start_btn.configure(text="▶  BAŞLAT", state="normal")

    def _close(self):
        if self.pipeline:
            self.pipeline.stop()
        self._collect()
        self.destroy()


def main():
    winapi.make_dpi_aware()
    App().mainloop()

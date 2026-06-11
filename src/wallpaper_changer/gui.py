"""Tkinter GUI for wallpaper-changer (lightweight)."""

from __future__ import annotations

import sys
import tkinter as tk
import tkinter.font as tkfont
from tkinter import ttk, filedialog, messagebox
from pathlib import Path
from typing import Optional

from wallpaper_changer.config import Config, MonitorConfig
from wallpaper_changer.i18n import init_i18n, set_language, get_language, t
from wallpaper_changer.monitor import Monitor, get_monitors
from wallpaper_changer.scheduler import WallpaperScheduler
from wallpaper_changer.source import WallpaperSource
from wallpaper_changer.systemd import install_service, uninstall_service, is_service_installed
from wallpaper_changer.wallpaper import (
    get_wallpaper, set_wallpaper, compose_multi_monitor_wallpaper,
)

# ── Color palette (GNOME-inspired) ──────────────────────────────────────────
COLORS = {
    "bg":           "#fafafa",
    "bg_dark":      "#f0f0f0",
    "surface":      "#ffffff",
    "border":       "#d5d5d5",
    "text":         "#2e3436",
    "text_dim":     "#77767b",
    "accent":       "#3584e4",
    "accent_hover": "#2a73c9",
    "success":      "#33d17a",
    "danger":       "#e01b24",
    "warning":      "#f5c211",
}


class MainWindow:
    """Main application window using Tkinter."""

    OPTIONS = ["scaled", "stretched", "zoom", "centered", "wallpaper", "spanned", "none"]

    def __init__(self) -> None:
        self.config = Config.load()
        init_i18n()
        if self.config.language:
            set_language(self.config.language)

        self.monitors: list[Monitor] = []
        self.scheduler = WallpaperScheduler(
            callback=self._on_scheduler_tick,
            interval=self.config.interval,
        )

        self.root = tk.Tk()
        self.root.title(t("app_title"))
        self.root.configure(bg=COLORS["bg"])

        # Force window to be visible and centered
        self.root.update_idletasks()
        w, h = 900, 650
        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()
        x = max(0, (sw - w) // 2)
        y = max(0, (sh - h) // 2)
        self.root.geometry(f"{w}x{h}+{x}+{y}")
        self.root.minsize(750, 520)

        # Ensure window is visible on Wayland
        self.root.deiconify()
        self.root.lift()
        self.root.focus_force()
        self.root.attributes('-topmost', True)
        self.root.update()
        self.root.attributes('-topmost', False)
        self.root.deiconify()
        self.root.lift()
        self.root.focus_force()
        self.root.update()

        self._setup_fonts()
        self._setup_styles()
        self._build_ui()
        self._refresh_monitors()

        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

        # Final focus after UI is built
        self.root.after(100, self._ensure_visible)

    # ── Font & style setup ──────────────────────────────────────────────────

    def _setup_fonts(self) -> None:
        sz = 13
        self.font_normal = tkfont.Font(family="Sans", size=sz)
        self.font_bold   = tkfont.Font(family="Sans", size=sz, weight="bold")
        self.font_small  = tkfont.Font(family="Sans", size=sz - 2)
        self.font_title  = tkfont.Font(family="Sans", size=sz + 1, weight="bold")
        self.font_btn    = tkfont.Font(family="Sans", size=sz, weight="bold")

    def _setup_styles(self) -> None:
        s = ttk.Style()
        s.theme_use("clam")

        # ── General
        s.configure(".", background=COLORS["bg"], foreground=COLORS["text"],
                    font=self.font_normal, borderwidth=0)

        # ── Notebook
        s.configure("TNotebook", background=COLORS["bg"], borderwidth=0, padding=4)
        s.configure("TNotebook.Tab",
                    background=COLORS["bg_dark"], foreground=COLORS["text"],
                    font=self.font_normal, padding=[16, 8], borderwidth=0)
        s.map("TNotebook.Tab",
              background=[("selected", COLORS["surface"])],
              foreground=[("selected", COLORS["accent"])])

        # ── Frames
        s.configure("TFrame", background=COLORS["bg"])
        s.configure("Card.TFrame", background=COLORS["surface"], relief="flat")

        # ── Labels
        s.configure("TLabel", background=COLORS["bg"], foreground=COLORS["text"],
                    font=self.font_normal)
        s.configure("Title.TLabel", font=self.font_title, foreground=COLORS["accent"])
        s.configure("Dim.TLabel", foreground=COLORS["text_dim"], font=self.font_small)
        s.configure("Card.TLabel", background=COLORS["surface"])

        # ── LabelFrame
        s.configure("TLabelframe", background=COLORS["surface"],
                    borderwidth=1, relief="solid", bordercolor=COLORS["border"])
        s.configure("TLabelframe.Label", background=COLORS["surface"],
                    foreground=COLORS["accent"], font=self.font_bold, padding=[8, 0])

        # ── Buttons
        s.configure("TButton", font=self.font_btn, padding=[14, 8],
                    background=COLORS["bg_dark"], foreground=COLORS["text"],
                    borderwidth=1, relief="solid", bordercolor=COLORS["border"])
        s.map("TButton",
              background=[("active", COLORS["border"])],
              bordercolor=[("active", COLORS["accent"])])

        s.configure("Accent.TButton", background=COLORS["accent"],
                    foreground="#ffffff", bordercolor=COLORS["accent"])
        s.map("Accent.TButton",
              background=[("active", COLORS["accent_hover"])],
              bordercolor=[("active", COLORS["accent_hover"])])

        s.configure("Danger.TButton", background=COLORS["danger"],
                    foreground="#ffffff", bordercolor=COLORS["danger"])
        s.map("Danger.TButton",
              background=[("active", "#c0101a")],
              bordercolor=[("active", "#c0101a")])

        # ── Entry / Spinbox
        s.configure("TEntry", font=self.font_normal, padding=6,
                    borderwidth=1, relief="solid", bordercolor=COLORS["border"])
        s.map("TEntry", bordercolor=[("focus", COLORS["accent"])])

        s.configure("TSpinbox", font=self.font_normal, padding=6,
                    borderwidth=1, relief="solid", bordercolor=COLORS["border"])
        s.map("TSpinbox", bordercolor=[("focus", COLORS["accent"])])

        # ── Combobox
        s.configure("TCombobox", font=self.font_normal, padding=6,
                    borderwidth=1, relief="solid", bordercolor=COLORS["border"])
        s.map("TCombobox", bordercolor=[("focus", COLORS["accent"])])

        # ── Checkbutton
        s.configure("TCheckbutton", background=COLORS["bg"], font=self.font_normal)

    # ── Layout ──────────────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        container = ttk.Frame(self.root)
        container.pack(fill=tk.BOTH, expand=True, padx=12, pady=12)

        self.notebook = ttk.Notebook(container)
        self.notebook.pack(fill=tk.BOTH, expand=True)

        self._build_preview_tab()
        self._build_sources_tab()
        self._build_timer_tab()
        self._build_settings_tab()

    # ── Card helper ─────────────────────────────────────────────────────────

    def _make_card(self, parent: ttk.Frame, title: str) -> ttk.LabelFrame:
        """Create a styled card-like LabelFrame."""
        card = ttk.LabelFrame(parent, text=f"  {title}  ", style="TLabelframe")
        card.pack(fill=tk.X, padx=0, pady=(0, 12))
        inner = ttk.Frame(card, style="Card.TFrame")
        inner.pack(fill=tk.BOTH, expand=True, padx=12, pady=12)
        return inner

    # ── Tab 1: Preview ──────────────────────────────────────────────────────

    def _build_preview_tab(self) -> None:
        tab = ttk.Frame(self.notebook, padding=16)
        self.notebook.add(tab, text=f"  {t('tab_preview')}  ")

        # Monitor info card
        card = self._make_card(tab, t("label_monitor"))
        self.monitor_listbox = tk.Listbox(
            card, height=4, font=self.font_normal,
            bg=COLORS["surface"], fg=COLORS["text"],
            selectbackground=COLORS["accent"], selectforeground="#fff",
            borderwidth=0, highlightthickness=1,
            highlightbackground=COLORS["border"], highlightcolor=COLORS["accent"],
            activestyle="none",
        )
        self.monitor_listbox.pack(fill=tk.X, pady=(0, 4))

        # Action buttons card
        card2 = self._make_card(tab, t("label_wallpaper"))

        btn_row = ttk.Frame(card2, style="Card.TFrame")
        btn_row.pack(fill=tk.X)

        self.btn_prev = ttk.Button(btn_row, text=t("btn_previous"), command=self._apply_random)
        self.btn_prev.pack(side=tk.LEFT, padx=(0, 8))

        self.btn_random = ttk.Button(btn_row, text=t("btn_random"),
                                     command=self._apply_random, style="Accent.TButton")
        self.btn_random.pack(side=tk.LEFT, padx=(0, 8))

        self.btn_next = ttk.Button(btn_row, text=t("btn_next"), command=self._apply_random)
        self.btn_next.pack(side=tk.LEFT)

        ttk.Button(btn_row, text=t("tray_quit"), command=self._quit,
                   style="Danger.TButton").pack(side=tk.RIGHT)

    # ── Tab 2: Sources ──────────────────────────────────────────────────────

    def _build_sources_tab(self) -> None:
        tab = ttk.Frame(self.notebook, padding=16)
        self.notebook.add(tab, text=f"  {t('tab_sources')}  ")

        self.source_outer = ttk.Frame(tab)
        self.source_outer.pack(fill=tk.BOTH, expand=True)

        self.source_frame = ttk.LabelFrame(
            self.source_outer, text=f"  {t('label_source_folder')}  ",
            style="TLabelframe",
        )
        self.source_frame.pack(fill=tk.BOTH, expand=True)

        self.source_rows: list[dict] = []

        btn_row = ttk.Frame(tab)
        btn_row.pack(fill=tk.X, pady=(12, 0))

        ttk.Button(btn_row, text=t("btn_refresh"),
                   command=self._refresh_monitors).pack(side=tk.LEFT)
        ttk.Button(btn_row, text=t("btn_save"),
                   command=self._save_sources, style="Accent.TButton").pack(side=tk.RIGHT)

    def _rebuild_source_rows(self) -> None:
        for row in self.source_rows:
            row["frame"].destroy()
        self.source_rows.clear()

        folder_map = {mc.name: mc.source_folder for mc in self.config.monitors}

        for m in self.monitors:
            frame = ttk.Frame(self.source_frame, style="Card.TFrame")
            frame.pack(fill=tk.X, padx=8, pady=6)

            primary = f"  {t('monitor_primary')}" if m.is_primary else ""
            icon = "🖥" if m.is_primary else "🖵"

            lbl = ttk.Label(frame, text=f"{icon}  {m.name}  {m.width}×{m.height}{primary}",
                            style="Card.TLabel", font=self.font_bold)
            lbl.pack(anchor=tk.W, pady=(0, 4))

            entry_row = ttk.Frame(frame, style="Card.TFrame")
            entry_row.pack(fill=tk.X)

            var = tk.StringVar(value=folder_map.get(m.name, ""))
            entry = ttk.Entry(entry_row, textvariable=var, font=self.font_normal)
            entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 8))

            def browse(v=var):
                path = filedialog.askdirectory()
                if path:
                    v.set(path)

            ttk.Button(entry_row, text=t("btn_browse"), command=browse).pack(side=tk.RIGHT)

            self.source_rows.append({"monitor": m, "var": var, "frame": frame})

    def _save_sources(self) -> None:
        for row in self.source_rows:
            folder = row["var"].get().strip()
            if not folder:
                continue
            mc = next((c for c in self.config.monitors if c.name == row["monitor"].name), None)
            if mc:
                mc.source_folder = folder
            else:
                self.config.monitors.append(
                    MonitorConfig(name=row["monitor"].name, source_folder=folder)
                )
        self.config.save()
        messagebox.showinfo("OK", t("msg_saved"))

    # ── Tab 3: Timer ────────────────────────────────────────────────────────

    def _build_timer_tab(self) -> None:
        tab = ttk.Frame(self.notebook, padding=16)
        self.notebook.add(tab, text=f"  {t('tab_timer')}  ")

        # Interval card
        card = self._make_card(tab, t("label_interval"))

        row = ttk.Frame(card, style="Card.TFrame")
        row.pack(fill=tk.X, pady=(0, 8))

        ttk.Label(row, text=t("label_change_every"), style="Card.TLabel").pack(side=tk.LEFT)

        self.interval_var = tk.IntVar(value=self.config.interval)
        spin = ttk.Spinbox(row, from_=10, to=86400, increment=10,
                           textvariable=self.interval_var, width=8, font=self.font_normal)
        spin.pack(side=tk.RIGHT)

        # Presets
        presets_row = ttk.Frame(card, style="Card.TFrame")
        presets_row.pack(fill=tk.X)

        for label, secs in [("1 min", 60), ("5 min", 300), ("30 min", 1800), ("1 hour", 3600)]:
            ttk.Button(presets_row, text=label,
                       command=lambda s=secs: self.interval_var.set(s)).pack(side=tk.LEFT, padx=(0, 8))

        # Scheduler card
        card2 = self._make_card(tab, t("label_scheduler"))

        status_row = ttk.Frame(card2, style="Card.TFrame")
        status_row.pack(fill=tk.X, pady=(0, 8))

        ttk.Label(status_row, text=t("label_status"), style="Card.TLabel").pack(side=tk.LEFT)

        self.status_var = tk.StringVar(value=t("status_stopped"))
        self.status_label = ttk.Label(status_row, textvariable=self.status_var,
                                      style="Dim.TLabel")
        self.status_label.pack(side=tk.LEFT, padx=8)

        btn_row = ttk.Frame(card2, style="Card.TFrame")
        btn_row.pack(fill=tk.X)

        ttk.Button(btn_row, text=t("btn_start"),
                   command=self._on_start, style="Accent.TButton").pack(side=tk.LEFT, padx=(0, 8))
        ttk.Button(btn_row, text=t("btn_stop"),
                   command=self._on_stop, style="Danger.TButton").pack(side=tk.LEFT)

        # Systemd card
        card3 = self._make_card(tab, t("label_systemd"))

        self.svc_var = tk.BooleanVar(value=is_service_installed())
        ttk.Checkbutton(card3, text=t("label_install_service"),
                        variable=self.svc_var,
                        command=self._on_service_toggle).pack(anchor=tk.W)

    def _on_start(self) -> None:
        interval = self.interval_var.get()
        self.config.interval = interval
        self.scheduler.interval = interval
        self.scheduler.start()
        self.status_var.set(t("status_running"))

    def _on_stop(self) -> None:
        self.scheduler.stop()
        self.status_var.set(t("status_stopped"))

    def _on_service_toggle(self) -> None:
        interval = self.interval_var.get()
        if self.svc_var.get():
            install_service(interval)
        else:
            uninstall_service()

    # ── Tab 4: Settings ─────────────────────────────────────────────────────

    def _build_settings_tab(self) -> None:
        tab = ttk.Frame(self.notebook, padding=16)
        self.notebook.add(tab, text=f"  {t('tab_settings')}  ")

        # Scaling card
        card = self._make_card(tab, t("label_scaling"))

        row = ttk.Frame(card, style="Card.TFrame")
        row.pack(fill=tk.X)

        ttk.Label(row, text=t("label_scaling_option"), style="Card.TLabel").pack(side=tk.LEFT)

        option_labels = [t(f"option_{opt}") for opt in self.OPTIONS]
        self.option_var = tk.StringVar(value=t(f"option_{self.config.option}"))
        combo = ttk.Combobox(row, textvariable=self.option_var, values=option_labels,
                             state="readonly", width=15, font=self.font_normal)
        combo.pack(side=tk.RIGHT)

        # Language card
        card2 = self._make_card(tab, t("label_language"))

        row2 = ttk.Frame(card2, style="Card.TFrame")
        row2.pack(fill=tk.X)

        ttk.Label(row2, text=t("label_language"), style="Card.TLabel").pack(side=tk.LEFT)

        self.lang_var = tk.StringVar(value="English" if get_language() == "en" else "中文")
        lang_combo = ttk.Combobox(row2, textvariable=self.lang_var,
                                  values=["English", "中文"], state="readonly",
                                  width=10, font=self.font_normal)
        lang_combo.pack(side=tk.RIGHT)
        lang_combo.bind("<<ComboboxSelected>>", self._on_language_changed)

        # Buttons
        btn_row = ttk.Frame(tab)
        btn_row.pack(fill=tk.X, pady=(12, 0))

        ttk.Button(btn_row, text=t("btn_reset"), command=self._on_reset).pack(side=tk.LEFT)
        ttk.Button(btn_row, text=t("btn_apply"),
                   command=self._on_apply, style="Accent.TButton").pack(side=tk.RIGHT)

    def _on_apply(self) -> None:
        label = self.option_var.get()
        for opt in self.OPTIONS:
            if t(f"option_{opt}") == label:
                self.config.option = opt
                break
        self.config.save()
        messagebox.showinfo("OK", t("msg_saved"))

    def _on_reset(self) -> None:
        self.config = Config.default()
        self.option_var.set(t(f"option_{self.config.option}"))
        self.interval_var.set(self.config.interval)

    def _on_language_changed(self, _event: object) -> None:
        lang = "zh" if self.lang_var.get() == "中文" else "en"
        set_language(lang)
        self.config.language = lang
        self.config.save()
        self._reload_ui()

    def _reload_ui(self) -> None:
        self.root.title(t("app_title"))
        self.notebook.tab(0, text=f"  {t('tab_preview')}  ")
        self.notebook.tab(1, text=f"  {t('tab_sources')}  ")
        self.notebook.tab(2, text=f"  {t('tab_timer')}  ")
        self.notebook.tab(3, text=f"  {t('tab_settings')}  ")
        self.btn_prev.config(text=t("btn_previous"))
        self.btn_random.config(text=t("btn_random"))
        self.btn_next.config(text=t("btn_next"))
        self.status_var.set(t("status_running") if self.scheduler.is_running() else t("status_stopped"))

    # ── Helpers ─────────────────────────────────────────────────────────────

    def _ensure_visible(self) -> None:
        """Ensure window is visible and focused (Wayland fix)."""
        self.root.deiconify()
        self.root.lift()
        self.root.focus_force()
        self.root.update_idletasks()

    def _refresh_monitors(self) -> None:
        try:
            self.monitors = get_monitors()
        except RuntimeError:
            self.monitors = []

        self.monitor_listbox.delete(0, tk.END)
        for m in self.monitors:
            primary = f"  {t('monitor_primary')}" if m.is_primary else ""
            self.monitor_listbox.insert(tk.END, f"  {m.name}   {m.width}×{m.height}{primary}")

        self._rebuild_source_rows()

    def _on_scheduler_tick(self) -> None:
        """Called by the scheduler on each interval."""
        monitors = get_monitors()
        if len(monitors) <= 1:
            for mc in self.config.monitors:
                src = WallpaperSource(mc.source_folder)
                img = src.get_random_image()
                if img:
                    set_wallpaper(str(img), self.config.option)
                    break
        else:
            images = []
            layout = []
            for monitor in monitors:
                mc = next((c for c in self.config.monitors if c.name == monitor.name), None)
                if mc and mc.source_folder:
                    src = WallpaperSource(mc.source_folder)
                    img = src.get_random_image()
                    if img:
                        images.append((str(img), monitor.width, monitor.height))
                        layout.append((monitor.x, monitor.y))
            if images:
                composed = compose_multi_monitor_wallpaper(
                    images, layout, mode=self.config.option, scaling=monitors[0].scaling,
                )
                set_wallpaper(composed, 'spanned')

    def _apply_random(self) -> None:
        monitors = get_monitors()
        if len(monitors) <= 1:
            for mc in self.config.monitors:
                src = WallpaperSource(mc.source_folder)
                img = src.get_random_image()
                if img:
                    set_wallpaper(str(img), self.config.option)
                    break
        else:
            images = []
            layout = []
            for monitor in monitors:
                mc = next((c for c in self.config.monitors if c.name == monitor.name), None)
                if mc and mc.source_folder:
                    src = WallpaperSource(mc.source_folder)
                    img = src.get_random_image()
                    if img:
                        images.append((str(img), monitor.width, monitor.height))
                        layout.append((monitor.x, monitor.y))
            if images:
                composed = compose_multi_monitor_wallpaper(
                    images, layout, mode=self.config.option, scaling=monitors[0].scaling,
                )
                set_wallpaper(composed, 'spanned')

    def _on_close(self) -> None:
        """Hide window instead of closing."""
        self.root.withdraw()
        self._show_minimized_indicator()

    def _show_minimized_indicator(self) -> None:
        """Show a small floating button to restore the window."""
        if hasattr(self, '_indicator') and self._indicator:
            try:
                self._indicator.destroy()
            except Exception:
                pass

        indicator = tk.Toplevel(self.root)
        indicator.title("")
        indicator.geometry("36x36+12+12")
        indicator.overrideredirect(True)
        indicator.attributes("-topmost", True)
        indicator.configure(bg=COLORS["accent"])

        btn = tk.Button(
            indicator, text="WC", font=("Sans", 10, "bold"),
            bg=COLORS["accent"], fg="#ffffff", bd=0, activebackground=COLORS["accent_hover"],
            activeforeground="#ffffff", cursor="hand2",
            command=lambda: self._restore_from_indicator(indicator),
        )
        btn.pack(fill=tk.BOTH, expand=True)
        self._indicator = indicator

    def _restore_from_indicator(self, indicator: tk.Toplevel) -> None:
        indicator.destroy()
        self._indicator = None
        self.root.deiconify()
        self.root.lift()

    def _quit(self) -> None:
        """Quit the application completely."""
        self.scheduler.stop()
        if hasattr(self, '_indicator') and self._indicator:
            try:
                self._indicator.destroy()
            except Exception:
                pass
        self.root.destroy()

    def run(self) -> None:
        self.root.mainloop()


def main() -> int:
    try:
        app = MainWindow()
        app.run()
        return 0
    except Exception as e:
        import traceback
        with open('/tmp/wallpaper-changer-error.log', 'w') as f:
            traceback.print_exc(file=f)
        raise


if __name__ == "__main__":
    raise SystemExit(main())

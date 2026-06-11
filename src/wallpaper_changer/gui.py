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

        # Detect display scaling factor for Wayland
        self.scale = self._detect_scale()
        w = int(800 * self.scale)
        h = int(600 * self.scale)
        self.root.geometry(f"{w}x{h}")
        self.root.minsize(int(650 * self.scale), int(450 * self.scale))

        # Force reasonable tk scaling (default can be too high on HiDPI)
        self.root.tk.call('tk', 'scaling', 1.5)

        base_font_size = max(14, int(14 * self.scale))

        default_font = tkfont.nametofont("TkDefaultFont")
        default_font.configure(size=base_font_size)
        self.root.option_add("*Font", default_font)

        style = ttk.Style()
        style.configure(".", font=("", base_font_size))
        style.configure("TButton", font=("", base_font_size), padding=8)
        style.configure("TLabel", font=("", base_font_size))
        style.configure("TNotebook.Tab", font=("", base_font_size), padding=[12, 6])
        style.configure("TLabelframe.Label", font=("", base_font_size, "bold"))
        style.configure("TCombobox", font=("", base_font_size))
        style.configure("TSpinbox", font=("", base_font_size))
        style.configure("TEntry", font=("", base_font_size))

        self._build_ui()
        self._refresh_monitors()

        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    # ---- layout -----------------------------------------------------------

    def _build_ui(self) -> None:
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)

        self._build_preview_tab()
        self._build_sources_tab()
        self._build_timer_tab()
        self._build_settings_tab()

    # ---- Tab 1: Preview ---------------------------------------------------

    def _build_preview_tab(self) -> None:
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text=t("tab_preview"))

        # Monitor list
        frame_monitors = ttk.LabelFrame(tab, text=t("label_monitor"))
        frame_monitors.pack(fill=tk.X, padx=8, pady=(8, 4))

        self.monitor_listbox = tk.Listbox(frame_monitors, height=4, font=("", 12))
        self.monitor_listbox.pack(fill=tk.X, padx=4, pady=4)

        # Buttons
        frame_btns = ttk.Frame(tab)
        frame_btns.pack(fill=tk.X, padx=8, pady=4)

        self.btn_prev = ttk.Button(frame_btns, text=t("btn_previous"), command=self._apply_random)
        self.btn_prev.pack(side=tk.LEFT, padx=4)

        self.btn_random = ttk.Button(frame_btns, text=t("btn_random"), command=self._apply_random)
        self.btn_random.pack(side=tk.LEFT, padx=4)

        self.btn_next = ttk.Button(frame_btns, text=t("btn_next"), command=self._apply_random)
        self.btn_next.pack(side=tk.LEFT, padx=4)

        # Quit button
        ttk.Button(frame_btns, text=t("tray_quit"), command=self._quit).pack(side=tk.RIGHT, padx=4)

    # ---- Tab 2: Sources ---------------------------------------------------

    def _build_sources_tab(self) -> None:
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text=t("tab_sources"))

        self.source_frame = ttk.LabelFrame(tab, text=t("label_source_folder"))
        self.source_frame.pack(fill=tk.BOTH, expand=True, padx=8, pady=(8, 4))

        self.source_rows: list[dict] = []

        frame_btns = ttk.Frame(tab)
        frame_btns.pack(fill=tk.X, padx=8, pady=4)

        ttk.Button(frame_btns, text=t("btn_save"), command=self._save_sources).pack(side=tk.RIGHT, padx=4)
        ttk.Button(frame_btns, text=t("btn_refresh"), command=self._refresh_monitors).pack(side=tk.RIGHT, padx=4)

    def _rebuild_source_rows(self) -> None:
        for row in self.source_rows:
            row["frame"].destroy()
        self.source_rows.clear()

        folder_map = {mc.name: mc.source_folder for mc in self.config.monitors}

        for m in self.monitors:
            frame = ttk.Frame(self.source_frame)
            frame.pack(fill=tk.X, padx=4, pady=2)

            primary = f" {t('monitor_primary')}" if m.is_primary else ""
            lbl = ttk.Label(frame, text=f"{m.name} ({m.width}x{m.height}{primary}):", width=28)
            lbl.pack(side=tk.LEFT)

            var = tk.StringVar(value=folder_map.get(m.name, ""))
            entry = ttk.Entry(frame, textvariable=var)
            entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=4)

            def browse(v=var):
                path = filedialog.askdirectory()
                if path:
                    v.set(path)

            ttk.Button(frame, text=t("btn_browse"), command=browse).pack(side=tk.LEFT)

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

    # ---- Tab 3: Timer -----------------------------------------------------

    def _build_timer_tab(self) -> None:
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text=t("tab_timer"))

        # Interval
        frame_interval = ttk.LabelFrame(tab, text=t("label_interval"))
        frame_interval.pack(fill=tk.X, padx=8, pady=(8, 4))

        row = ttk.Frame(frame_interval)
        row.pack(fill=tk.X, padx=4, pady=4)

        ttk.Label(row, text=t("label_change_every")).pack(side=tk.LEFT)

        self.interval_var = tk.IntVar(value=self.config.interval)
        spin = ttk.Spinbox(row, from_=10, to=86400, increment=10,
                           textvariable=self.interval_var, width=8)
        spin.pack(side=tk.LEFT, padx=8)

        # Presets
        frame_presets = ttk.Frame(frame_interval)
        frame_presets.pack(fill=tk.X, padx=4, pady=(0, 4))

        for label, secs in [("1 min", 60), ("5 min", 300), ("30 min", 1800), ("1 hour", 3600)]:
            ttk.Button(frame_presets, text=label,
                       command=lambda s=secs: self.interval_var.set(s)).pack(side=tk.LEFT, padx=4)

        # Scheduler
        frame_sched = ttk.LabelFrame(tab, text=t("label_scheduler"))
        frame_sched.pack(fill=tk.X, padx=8, pady=4)

        row2 = ttk.Frame(frame_sched)
        row2.pack(fill=tk.X, padx=4, pady=4)

        ttk.Label(row2, text=t("label_status")).pack(side=tk.LEFT)
        self.status_var = tk.StringVar(value=t("status_stopped"))
        ttk.Label(row2, textvariable=self.status_var).pack(side=tk.LEFT, padx=8)

        row3 = ttk.Frame(frame_sched)
        row3.pack(fill=tk.X, padx=4, pady=(0, 4))

        ttk.Button(row3, text=t("btn_start"), command=self._on_start).pack(side=tk.LEFT, padx=4)
        ttk.Button(row3, text=t("btn_stop"), command=self._on_stop).pack(side=tk.LEFT, padx=4)

        # Systemd
        frame_svc = ttk.LabelFrame(tab, text=t("label_systemd"))
        frame_svc.pack(fill=tk.X, padx=8, pady=4)

        self.svc_var = tk.BooleanVar(value=is_service_installed())
        ttk.Checkbutton(frame_svc, text=t("label_install_service"),
                        variable=self.svc_var, command=self._on_service_toggle).pack(padx=4, pady=4)

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

    # ---- Tab 4: Settings --------------------------------------------------

    def _build_settings_tab(self) -> None:
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text=t("tab_settings"))

        # Scaling option
        frame_scaling = ttk.LabelFrame(tab, text=t("label_scaling"))
        frame_scaling.pack(fill=tk.X, padx=8, pady=(8, 4))

        row = ttk.Frame(frame_scaling)
        row.pack(fill=tk.X, padx=4, pady=4)

        ttk.Label(row, text=t("label_scaling_option")).pack(side=tk.LEFT)

        option_labels = [t(f"option_{opt}") for opt in self.OPTIONS]
        self.option_var = tk.StringVar(value=t(f"option_{self.config.option}"))
        combo = ttk.Combobox(row, textvariable=self.option_var, values=option_labels,
                             state="readonly", width=15)
        combo.pack(side=tk.LEFT, padx=8)

        # Language
        frame_lang = ttk.LabelFrame(tab, text=t("label_language"))
        frame_lang.pack(fill=tk.X, padx=8, pady=4)

        row2 = ttk.Frame(frame_lang)
        row2.pack(fill=tk.X, padx=4, pady=4)

        ttk.Label(row2, text=t("label_language")).pack(side=tk.LEFT)

        self.lang_var = tk.StringVar(value="English" if get_language() == "en" else "中文")
        lang_combo = ttk.Combobox(row2, textvariable=self.lang_var,
                                  values=["English", "中文"], state="readonly", width=10)
        lang_combo.pack(side=tk.LEFT, padx=8)
        lang_combo.bind("<<ComboboxSelected>>", self._on_language_changed)

        # Apply / Reset
        frame_btns = ttk.Frame(tab)
        frame_btns.pack(fill=tk.X, padx=8, pady=8)

        ttk.Button(frame_btns, text=t("btn_apply"), command=self._on_apply).pack(side=tk.RIGHT, padx=4)
        ttk.Button(frame_btns, text=t("btn_reset"), command=self._on_reset).pack(side=tk.RIGHT, padx=4)

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
        self.notebook.tab(0, text=t("tab_preview"))
        self.notebook.tab(1, text=t("tab_sources"))
        self.notebook.tab(2, text=t("tab_timer"))
        self.notebook.tab(3, text=t("tab_settings"))
        self.btn_prev.config(text=t("btn_previous"))
        self.btn_random.config(text=t("btn_random"))
        self.btn_next.config(text=t("btn_next"))
        self.status_var.set(t("status_running") if self.scheduler.is_running() else t("status_stopped"))

    # ---- helpers ----------------------------------------------------------

    def _detect_scale(self) -> float:
        """Detect display scaling factor from monitors."""
        try:
            monitors = get_monitors()
            if monitors:
                return monitors[0].scaling
        except Exception:
            pass
        return 1.0

    def _refresh_monitors(self) -> None:
        try:
            self.monitors = get_monitors()
        except RuntimeError:
            self.monitors = []

        self.monitor_listbox.delete(0, tk.END)
        for m in self.monitors:
            primary = f"  {t('monitor_primary')}" if m.is_primary else ""
            self.monitor_listbox.insert(tk.END, f"{m.name}  {m.width}x{m.height}{primary}")

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

        # Show a notification-like window that can restore the main window
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
        indicator.geometry("30x30+10+10")
        indicator.overrideredirect(True)
        indicator.attributes("-topmost", True)

        btn = tk.Button(indicator, text="WC", font=("", 10, "bold"),
                        bg="#3584e4", fg="white", bd=0,
                        command=lambda: self._restore_from_indicator(indicator))
        btn.pack(fill=tk.BOTH, expand=True)

        self._indicator = indicator

    def _restore_from_indicator(self, indicator: tk.Toplevel) -> None:
        """Restore window from minimized indicator."""
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
        """Run the main loop."""
        self.root.mainloop()


def main() -> int:
    app = MainWindow()
    app.run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

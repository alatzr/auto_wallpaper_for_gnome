"""GTK4 + libadwaita GUI for wallpaper-changer."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Optional

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gdk, GdkPixbuf, Gio, GLib, Gtk

from wallpaper_changer.config import Config, MonitorConfig
from wallpaper_changer.i18n import get_language, init_i18n, set_language, t
from wallpaper_changer.monitor import Monitor, get_monitors
from wallpaper_changer.scheduler import WallpaperScheduler
from wallpaper_changer.source import IMAGE_EXTENSIONS, WallpaperSource
from wallpaper_changer.systemd import (
    install_service,
    is_service_installed,
    uninstall_service,
)
from wallpaper_changer.wallpaper import compose_multi_monitor_wallpaper, get_wallpaper, set_wallpaper


# ---------------------------------------------------------------------------
# System Tray Icon (D-Bus StatusNotifierItem)
# ---------------------------------------------------------------------------

SNI_INTERFACE = """
<node>
  <interface name="org.freedesktop.StatusNotifierItem">
    <property name="Id" type="s" access="read"/>
    <property name="Title" type="s" access="read"/>
    <property name="Status" type="s" access="read"/>
    <property name="IconName" type="s" access="read"/>
    <property name="Menu" type="o" access="read"/>
    <signal name="NewIcon"/>
    <signal name="NewStatus"/>
    <method name="Activate">
      <arg direction="in" name="x" type="i"/>
      <arg direction="in" name="y" type="i"/>
    </method>
    <method name="SecondaryActivate">
      <arg direction="in" name="x" type="i"/>
      <arg direction="in" name="y" type="i"/>
    </method>
    <method name="ContextMenu">
      <arg direction="in" name="x" type="i"/>
      <arg direction="in" name="y" type="i"/>
    </method>
  </interface>
</node>
"""

DBUSMENU_INTERFACE = """
<node>
  <interface name="com.canonical.dbusmenu">
    <method name="GetLayout">
      <arg direction="in" name="parentId" type="i"/>
      <arg direction="in" name="recursionDepth" type="i"/>
      <arg direction="in" name="propertyNames" type="as"/>
      <arg direction="out" name="revision" type="u"/>
      <arg direction="out" name="layout" type="(ia{sv}av)"/>
    </method>
    <method name="GetProperties">
      <arg direction="in" name="ids" type="ai"/>
      <arg direction="out" name="properties" type="aa{sv}"/>
    </method>
    <method name="Event">
      <arg direction="in" name="eventId" type="i"/>
      <arg direction="in" name="event" type="s"/>
      <arg direction="in" name="data" type="v"/>
      <arg direction="in" name="timestamp" type="u"/>
    </method>
    <signal name="LayoutUpdated">
      <arg name="revision" type="u"/>
      <arg name="parent" type="i"/>
    </signal>
  </interface>
</node>
"""


class TrayIcon:
    """System tray icon using D-Bus StatusNotifierItem (GTK4-compatible)."""

    def __init__(self, app: "WallpaperChangerApp") -> None:
        self.app = app
        self._connection: Optional[Gio.DBusConnection] = None
        self._sni_registration_id = 0
        self._menu_registration_id = 0
        self._bus_owner_id = 0
        self._menu_revision = 1
        self._paused = False
        self._visible = True

    def start(self) -> None:
        """Register the tray icon on the session bus."""
        self._bus_owner_id = Gio.bus_own_name(
            Gio.BusType.SESSION,
            "org.kde.StatusNotifierItem",
            Gio.BusNameOwnerFlags.NONE,
            self._on_bus_acquired,
            None,
            None,
        )

    def stop(self) -> None:
        """Unregister the tray icon."""
        if self._bus_owner_id:
            Gio.bus_unown_name(self._bus_owner_id)
            self._bus_owner_id = 0
        if self._sni_registration_id and self._connection:
            self._connection.unregister_object(self._sni_registration_id)
            self._sni_registration_id = 0
        if self._menu_registration_id and self._connection:
            self._connection.unregister_object(self._menu_registration_id)
            self._menu_registration_id = 0

    def set_paused(self, paused: bool) -> None:
        self._paused = paused
        self._menu_revision += 1
        self._emit_layout_updated()

    def set_visible(self, visible: bool) -> None:
        self._visible = visible
        if self._connection:
            self._connection.emit_signal(
                None,
                "/StatusNotifierItem",
                "org.freedesktop.StatusNotifierItem",
                "NewStatus",
                GLib.Variant.new_tuple(GLib.Variant("s", self._get_status())),
            )

    def _get_status(self) -> str:
        return "Active" if self._visible else "Passive"

    def _on_bus_acquired(
        self, connection: Gio.DBusConnection, name: str
    ) -> None:
        self._connection = connection
        node_info_sni = Gio.DBusNodeInfo.new_for_xml(SNI_INTERFACE)
        node_info_menu = Gio.DBusNodeInfo.new_for_xml(DBUSMENU_INTERFACE)

        self._sni_registration_id = connection.register_object(
            "/StatusNotifierItem",
            node_info_sni.interfaces[0],
            self._handle_sni_method,
            None,
            None,
        )

        self._menu_registration_id = connection.register_object(
            "/StatusNotifierItem/menu",
            node_info_menu.interfaces[0],
            self._handle_menu_method,
            None,
            None,
        )

        # Register with the StatusNotifierWatcher
        try:
            watcher = Gio.DBusProxy.new_for_bus_sync(
                Gio.BusType.SESSION,
                Gio.DBusProxyFlags.NONE,
                None,
                "org.kde.StatusNotifierWatcher",
                "/StatusNotifierWatcher",
                "org.kde.StatusNotifierWatcher",
                None,
            )
            # Call RegisterStatusNotifierItem with correct GVariant format
            watcher.call_sync(
                "RegisterStatusNotifierItem",
                GLib.Variant("(s)", ("/StatusNotifierItem",)),
                Gio.DBusCallFlags.NONE,
                -1,
                None,
            )
        except GLib.Error:
            # No watcher available; try X11 fallback or just skip
            pass

    def _handle_sni_method(
        self,
        connection: Gio.DBusConnection,
        sender: str,
        object_path: str,
        interface_name: str,
        method_name: str,
        parameters: GLib.Variant,
        invocation: Gio.DBusMethodInvocation,
    ) -> None:
        if method_name == "Activate":
            GLib.idle_add(self._on_activate)
            invocation.return_value(None)
        elif method_name == "SecondaryActivate":
            GLib.idle_add(self._on_next_wallpaper)
            invocation.return_value(None)
        elif method_name == "ContextMenu":
            # Context menu is handled via the Menu property
            invocation.return_value(None)
        else:
            invocation.return_value(None)

    def _handle_menu_method(
        self,
        connection: Gio.DBusConnection,
        sender: str,
        object_path: str,
        interface_name: str,
        method_name: str,
        parameters: GLib.Variant,
        invocation: Gio.DBusMethodInvocation,
    ) -> None:
        if method_name == "GetLayout":
            parent_id = parameters.get_child_value(0).get_int32()
            revision, layout = self._get_menu_layout(parent_id)
            invocation.return_value(
                GLib.Variant.new_tuple(
                    GLib.Variant("u", revision),
                    layout,
                )
            )
        elif method_name == "GetProperties":
            ids = parameters.get_child_value(0)
            props = self._get_menu_properties(ids)
            invocation.return_value(GLib.Variant.new_tuple(props))
        elif method_name == "Event":
            event_id = parameters.get_child_value(0).get_int32()
            event = parameters.get_child_value(1).get_string()
            if event == "clicked":
                GLib.idle_add(self._on_menu_clicked, event_id)
            invocation.return_value(None)
        else:
            invocation.return_value(None)

    def _get_menu_layout(
        self, parent_id: int
    ) -> tuple[int, GLib.Variant]:
        if parent_id != 0:
            return (self._menu_revision, self._build_empty_layout())

        pause_label = t("tray_resume") if self._paused else t("tray_pause")
        children = [
            self._make_menu_item(1, t("tray_next"), t("tray_next")),
            self._make_menu_item(2, pause_label, pause_label),
            self._make_menu_separator(3),
            self._make_menu_item(4, t("tray_show"), t("tray_show")),
            self._make_menu_separator(5),
            self._make_menu_item(6, t("tray_quit"), t("tray_quit")),
        ]

        layout = GLib.Variant(
            "(ia{sv}av)",
            (
                0,
                {"children-display": GLib.Variant("s", "list")},
                children,
            ),
        )
        return (self._menu_revision, layout)

    def _build_empty_layout(self) -> GLib.Variant:
        return GLib.Variant(
            "(ia{sv}av)", (0, {}, [])
        )

    def _make_menu_item(
        self, item_id: int, label: str, description: str
    ) -> GLib.Variant:
        return GLib.Variant(
            "(ia{sv}av)",
            (
                item_id,
                {
                    "label": GLib.Variant("s", label),
                    "children-display": GLib.Variant("s", "none"),
                },
                [],
            ),
        )

    def _make_menu_separator(self, item_id: int) -> GLib.Variant:
        return GLib.Variant(
            "(ia{sv}av)",
            (item_id, {"type": GLib.Variant("s", "separator")}, []),
        )

    def _get_menu_properties(self, ids: GLib.Variant) -> GLib.Variant:
        result = []
        for i in range(ids.n_children()):
            item_id = ids.get_child_value(i).get_int32()
            props = self._get_item_properties(item_id)
            result.append(props)
        return GLib.Variant("aa{sv}", result)

    def _get_item_properties(self, item_id: int) -> GLib.Variant:
        pause_label = t("tray_resume") if self._paused else t("tray_pause")
        items = {
            1: {"label": GLib.Variant("s", t("tray_next"))},
            2: {"label": GLib.Variant("s", pause_label)},
            4: {"label": GLib.Variant("s", t("tray_show"))},
            6: {"label": GLib.Variant("s", t("tray_quit"))},
        }
        return GLib.Variant("a{sv}", items.get(item_id, {}))

    def _on_menu_clicked(self, item_id: int) -> None:
        if item_id == 1:
            self._on_next_wallpaper()
        elif item_id == 2:
            self._on_toggle_pause()
        elif item_id == 4:
            self._on_activate()
        elif item_id == 6:
            self._on_quit()

    def _emit_layout_updated(self) -> None:
        if self._connection:
            self._connection.emit_signal(
                None,
                "/StatusNotifierItem/menu",
                "com.canonical.dbusmenu",
                "LayoutUpdated",
                GLib.Variant.new_tuple(
                    GLib.Variant("u", self._menu_revision),
                    GLib.Variant("i", 0),
                ),
            )

    def _on_activate(self) -> None:
        win = self.app.win
        if win:
            if win.is_visible():
                win.hide()
            else:
                win.present()

    def _on_next_wallpaper(self) -> None:
        win = self.app.win
        if win:
            for mc in win.config.monitors:
                src = WallpaperSource(mc.source_folder)
                img = src.get_random_image()
                if img:
                    set_wallpaper(str(img), win.config.option)
                    break

    def _on_toggle_pause(self) -> None:
        win = self.app.win
        if win:
            if win.scheduler.is_running():
                win.scheduler.stop()
                self._paused = True
                if hasattr(win, "timer_tab"):
                    win.timer_tab.status_label.set_text(t("status_paused"))
            else:
                interval = win.config.interval
                win.scheduler.interval = interval
                win.scheduler.start()
                self._paused = False
                if hasattr(win, "timer_tab"):
                    win.timer_tab.status_label.set_text(t("status_running"))
            self._menu_revision += 1
            self._emit_layout_updated()

    def _on_quit(self) -> None:
        win = self.app.win
        if win:
            win.scheduler.stop()
        self.stop()
        self.app.quit()


# ---------------------------------------------------------------------------
# Application
# ---------------------------------------------------------------------------


class WallpaperChangerApp(Adw.Application):
    """Main application class."""

    def __init__(self) -> None:
        super().__init__(application_id="com.github.wallpaper-changer")
        self.win: Optional[MainWindow] = None
        self.tray: Optional[TrayIcon] = None
        self.connect("activate", self.on_activate)
        self.connect("shutdown", self.on_shutdown)

    def on_activate(self, app: Adw.Application) -> None:
        self.win = MainWindow(application=app)
        self.win.present()

        self.tray = TrayIcon(self)
        self.tray.start()

    def on_shutdown(self, app: Adw.Application) -> None:
        if self.tray:
            self.tray.stop()


# ---------------------------------------------------------------------------
# Main Window
# ---------------------------------------------------------------------------


class MainWindow(Adw.ApplicationWindow):
    """Main application window."""

    def __init__(self, **kwargs: object) -> None:
        super().__init__(**kwargs)
        self.config = Config.load()
        init_i18n()
        if self.config.language:
            set_language(self.config.language)
        self.set_title(t("app_title"))
        self.set_default_size(800, 600)

        self.monitors: list[Monitor] = []
        self.scheduler = WallpaperScheduler(
            callback=self._on_scheduler_tick,
            interval=self.config.interval,
        )

        self._build_ui()
        self._refresh_monitors()

        self.connect("close-request", self._on_close_request)

    # ---- layout -----------------------------------------------------------

    def _build_ui(self) -> None:
        toolbar_view = Adw.ToolbarView()
        self.set_content(toolbar_view)

        header = Adw.HeaderBar()
        toolbar_view.add_top_bar(header)

        menu_button = Gtk.MenuButton()
        menu_button.set_icon_name("open-menu-symbolic")
        menu_model = Gio.Menu()
        menu_model.append(t("menu_about"), "win.about")
        menu_button.set_menu_model(menu_model)
        header.pack_end(menu_button)

        about_action = Gio.SimpleAction.new("about", None)
        about_action.connect("activate", self._on_about)
        self.add_action(about_action)

        self.notebook = Gtk.Notebook()
        self.notebook.set_vexpand(True)
        toolbar_view.set_content(self.notebook)

        self.preview_tab = PreviewTab(self)
        self.source_tab = SourceTab(self)
        self.timer_tab = TimerTab(self)
        self.settings_tab = SettingsTab(self)

        self.notebook.append_page(self.preview_tab, Gtk.Label(label=t("tab_preview")))
        self.notebook.append_page(self.source_tab, Gtk.Label(label=t("tab_sources")))
        self.notebook.append_page(self.timer_tab, Gtk.Label(label=t("tab_timer")))
        self.notebook.append_page(self.settings_tab, Gtk.Label(label=t("tab_settings")))

    # ---- helpers ----------------------------------------------------------

    def _refresh_monitors(self) -> None:
        try:
            self.monitors = get_monitors()
        except RuntimeError:
            self.monitors = []
        self.preview_tab.refresh(self.monitors)
        self.source_tab.refresh(self.monitors, self.config)

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

    def reload_ui(self) -> None:
        """Reload all UI text after language change."""
        self.set_title(t("app_title"))
        self.notebook.set_tab_label(self.preview_tab, Gtk.Label(label=t("tab_preview")))
        self.notebook.set_tab_label(self.source_tab, Gtk.Label(label=t("tab_sources")))
        self.notebook.set_tab_label(self.timer_tab, Gtk.Label(label=t("tab_timer")))
        self.notebook.set_tab_label(self.settings_tab, Gtk.Label(label=t("tab_settings")))
        self.preview_tab.reload_ui()
        self.source_tab.reload_ui()
        self.timer_tab.reload_ui()
        self.settings_tab.reload_ui()

    def _on_about(self, _action: Gio.SimpleAction, _param: None) -> None:
        about = Adw.AboutWindow(
            transient_for=self,
            application_name="Wallpaper Changer",
            version="0.1.0",
            comments="Automatic wallpaper rotation for GNOME",
            license_type=Gtk.License.MIT_X11,
        )
        about.present()

    def _on_close_request(self, _win: Gtk.Window) -> bool:
        if self.config.minimize_to_tray:
            self.hide()
            return True
        return False


# ---------------------------------------------------------------------------
# Tab 1 – Preview & Switch
# ---------------------------------------------------------------------------


class PreviewTab(Gtk.Box):
    """Tab for wallpaper preview and switching."""

    def __init__(self, main_win: MainWindow) -> None:
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        self.set_margin_top(12)
        self.set_margin_bottom(12)
        self.set_margin_start(12)
        self.set_margin_end(12)
        self.main_win = main_win
        self._build()

    def _build(self) -> None:
        self.picture = Gtk.Picture()
        self.picture.set_can_shrink(True)
        self.picture.set_size_request(-1, 300)
        self.append(self.picture)

        scrolled = Gtk.ScrolledWindow()
        scrolled.set_vexpand(True)
        scrolled.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        self.monitor_list = Gtk.ListBox()
        self.monitor_list.set_selection_mode(Gtk.SelectionMode.SINGLE)
        scrolled.set_child(self.monitor_list)
        self.append(scrolled)

        btn_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        btn_box.set_halign(Gtk.Align.CENTER)
        self.append(btn_box)

        self.btn_prev = Gtk.Button(label=t("btn_previous"))
        self.btn_prev.connect("clicked", self._on_prev)
        btn_box.append(self.btn_prev)

        self.btn_random = Gtk.Button(label=t("btn_random"))
        self.btn_random.add_css_class("suggested-action")
        self.btn_random.connect("clicked", self._on_random)
        btn_box.append(self.btn_random)

        self.btn_next = Gtk.Button(label=t("btn_next"))
        self.btn_next.connect("clicked", self._on_next)
        btn_box.append(self.btn_next)

        self._refresh_preview()

    def refresh(self, monitors: list[Monitor]) -> None:
        while row := self.monitor_list.get_row_at_index(0):
            self.monitor_list.remove(row)
        for m in monitors:
            primary_text = f"  {t('monitor_primary')}" if m.is_primary else ""
            label = Gtk.Label(label=f"{m.name}  {m.width}x{m.height}{primary_text}")
            label.set_xalign(0)
            self.monitor_list.append(label)

    def reload_ui(self) -> None:
        self.btn_prev.set_label(t("btn_previous"))
        self.btn_random.set_label(t("btn_random"))
        self.btn_next.set_label(t("btn_next"))

    def _refresh_preview(self) -> None:
        wp = get_wallpaper()
        if wp and Path(wp).is_file():
            self.picture.set_filename(wp)

    def _get_selected_source(self) -> Optional[WallpaperSource]:
        cfg = self.main_win.config
        if cfg.monitors:
            return WallpaperSource(cfg.monitors[0].source_folder)
        return None

    def _apply_random(self) -> None:
        monitors = get_monitors()
        if len(monitors) <= 1:
            src = self._get_selected_source()
            if src:
                img = src.get_random_image()
                if img:
                    set_wallpaper(str(img), self.main_win.config.option)
        else:
            images = []
            layout = []
            for monitor in monitors:
                mc = next(
                    (c for c in self.main_win.config.monitors if c.name == monitor.name),
                    None,
                )
                if mc and mc.source_folder:
                    src = WallpaperSource(mc.source_folder)
                    img = src.get_random_image()
                    if img:
                        images.append((str(img), monitor.width, monitor.height))
                        layout.append((monitor.x, monitor.y))
            if images:
                composed = compose_multi_monitor_wallpaper(
                    images, layout, mode=self.main_win.config.option, scaling=monitors[0].scaling,
                )
                set_wallpaper(composed, 'spanned')
        self._refresh_preview()

    def _on_prev(self, _btn: Gtk.Button) -> None:
        self._apply_random()

    def _on_next(self, _btn: Gtk.Button) -> None:
        self._apply_random()

    def _on_random(self, _btn: Gtk.Button) -> None:
        self._apply_random()


# ---------------------------------------------------------------------------
# Tab 2 – Source Folder Management
# ---------------------------------------------------------------------------


class SourceTab(Gtk.Box):
    """Tab for managing wallpaper source folders."""

    def __init__(self, main_win: MainWindow) -> None:
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        self.set_margin_top(12)
        self.set_margin_bottom(12)
        self.set_margin_start(12)
        self.set_margin_end(12)
        self.main_win = main_win
        self.rows: list[SourceRow] = []
        self._build()

    def _build(self) -> None:
        scrolled = Gtk.ScrolledWindow()
        scrolled.set_vexpand(True)
        self.list_box = Gtk.ListBox()
        self.list_box.set_selection_mode(Gtk.SelectionMode.NONE)
        scrolled.set_child(self.list_box)
        self.append(scrolled)

        btn_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        btn_box.set_halign(Gtk.Align.END)
        self.append(btn_box)

        self.btn_add = Gtk.Button(label=t("btn_add_folder"))
        self.btn_add.add_css_class("suggested-action")
        self.btn_add.connect("clicked", self._on_add)
        btn_box.append(self.btn_add)

        self.btn_save = Gtk.Button(label=t("btn_save"))
        self.btn_save.connect("clicked", self._on_save)
        btn_box.append(self.btn_save)

    def refresh(self, monitors: list[Monitor], config: Config) -> None:
        for row in self.rows:
            self.list_box.remove(row)
        self.rows.clear()

        folder_map = {mc.name: mc.source_folder for mc in config.monitors}

        for m in monitors:
            row = SourceRow(m, folder_map.get(m.name, ""))
            self.rows.append(row)
            self.list_box.append(row)

    def _on_add(self, _btn: Gtk.Button) -> None:
        dialog = Gtk.FileDialog()
        dialog.set_title("Select Wallpaper Folder")
        dialog.select_folder(self.main_win, None, self._on_folder_selected)

    def _on_folder_selected(self, dialog: Gtk.FileDialog, result: Gio.AsyncResult) -> None:
        try:
            folder = dialog.select_folder_finish(result)
        except GLib.Error:
            return
        if folder:
            path = folder.get_path()
            if path:
                cfg = self.main_win.config
                if not cfg.monitors:
                    name = self.main_win.monitors[0].name if self.main_win.monitors else "default"
                    cfg.monitors.append(MonitorConfig(name=name, source_folder=path))
                else:
                    cfg.monitors[0].source_folder = path
                self.refresh(self.main_win.monitors, cfg)

    def _on_save(self, _btn: Gtk.Button) -> None:
        for row in self.rows:
            for mc in self.main_win.config.monitors:
                if mc.name == row.monitor.name:
                    mc.source_folder = row.get_folder()
                    break
            else:
                self.main_win.config.monitors.append(
                    MonitorConfig(name=row.monitor.name, source_folder=row.get_folder())
                )
        self.main_win.config.save()

    def reload_ui(self) -> None:
        self.btn_add.set_label(t("btn_add_folder"))
        self.btn_save.set_label(t("btn_save"))


class SourceRow(Gtk.Box):
    """Single row for a monitor's source folder."""

    def __init__(self, monitor: Monitor, folder: str) -> None:
        super().__init__(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        self.monitor = monitor
        self.set_margin_top(4)
        self.set_margin_bottom(4)

        label = Gtk.Label(label=f"{monitor.name}:")
        label.set_xalign(0)
        label.set_size_request(120, -1)
        self.append(label)

        self.entry = Gtk.Entry()
        self.entry.set_hexpand(True)
        self.entry.set_text(folder)
        self.append(self.entry)

        self.btn_browse = Gtk.Button(label=t("btn_browse"))
        self.btn_browse.connect("clicked", self._on_browse)
        self.append(self.btn_browse)

    def get_folder(self) -> str:
        return self.entry.get_text()

    def _on_browse(self, _btn: Gtk.Button) -> None:
        dialog = Gtk.FileDialog()
        dialog.set_title("Select Folder")
        dialog.select_folder(None, None, self._on_selected)

    def _on_selected(self, dialog: Gtk.FileDialog, result: Gio.AsyncResult) -> None:
        try:
            folder = dialog.select_folder_finish(result)
        except GLib.Error:
            return
        if folder:
            path = folder.get_path()
            if path:
                self.entry.set_text(path)


# ---------------------------------------------------------------------------
# Tab 3 – Timer Settings
# ---------------------------------------------------------------------------


class TimerTab(Gtk.Box):
    """Tab for timer settings."""

    def __init__(self, main_win: MainWindow) -> None:
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        self.set_margin_top(12)
        self.set_margin_bottom(12)
        self.set_margin_start(12)
        self.set_margin_end(12)
        self.main_win = main_win
        self._build()

    def _build(self) -> None:
        group = Adw.PreferencesGroup(title=t("label_interval"))
        self.append(group)

        row = Adw.ActionRow(title=t("label_change_every"))
        self.spin = Gtk.SpinButton.new_with_range(10, 86400, 10)
        self.spin.set_value(self.main_win.config.interval)
        row.add_suffix(self.spin)
        group.add(row)

        presets_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        presets_box.set_halign(Gtk.Align.CENTER)
        self.append(presets_box)

        for label, secs in [("1 min", 60), ("5 min", 300), ("30 min", 1800), ("1 hour", 3600)]:
            btn = Gtk.Button(label=label)
            btn.connect("clicked", self._on_preset, secs)
            presets_box.append(btn)

        group2 = Adw.PreferencesGroup(title=t("label_scheduler"))
        self.append(group2)

        self.status_label = Gtk.Label(label=t("status_stopped"))
        self.status_label.set_xalign(0)
        status_row = Adw.ActionRow(title=t("label_status"))
        status_row.add_suffix(self.status_label)
        group2.add(status_row)

        btn_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        btn_box.set_halign(Gtk.Align.CENTER)
        self.append(btn_box)

        self.btn_start = Gtk.Button(label=t("btn_start"))
        self.btn_start.add_css_class("suggested-action")
        self.btn_start.connect("clicked", self._on_start)
        btn_box.append(self.btn_start)

        self.btn_stop = Gtk.Button(label=t("btn_stop"))
        self.btn_stop.add_css_class("destructive-action")
        self.btn_stop.connect("clicked", self._on_stop)
        btn_box.append(self.btn_stop)

        group3 = Adw.PreferencesGroup(title=t("label_systemd"))
        self.append(group3)

        svc_row = Adw.ActionRow(title=t("label_install_service"))
        self.svc_switch = Gtk.Switch()
        self.svc_switch.set_active(is_service_installed())
        self.svc_switch.set_valign(Gtk.Align.CENTER)
        self.svc_switch.connect("state-set", self._on_service_toggle)
        svc_row.add_suffix(self.svc_switch)
        group3.add(svc_row)

    def _on_preset(self, _btn: Gtk.Button, secs: int) -> None:
        self.spin.set_value(secs)

    def _on_start(self, _btn: Gtk.Button) -> None:
        interval = int(self.spin.get_value())
        self.main_win.config.interval = interval
        self.main_win.scheduler.interval = interval
        self.main_win.scheduler.start()
        self.status_label.set_text(t("status_running"))

    def _on_stop(self, _btn: Gtk.Button) -> None:
        self.main_win.scheduler.stop()
        self.status_label.set_text(t("status_stopped"))

    def _on_service_toggle(self, _sw: Gtk.Switch, active: bool) -> None:
        interval = int(self.spin.get_value())
        if active:
            install_service(interval)
        else:
            uninstall_service()

    def reload_ui(self) -> None:
        self.btn_start.set_label(t("btn_start"))
        self.btn_stop.set_label(t("btn_stop"))


# ---------------------------------------------------------------------------
# Tab 4 – General Settings
# ---------------------------------------------------------------------------


class SettingsTab(Gtk.Box):
    """Tab for general settings."""

    OPTIONS = ["scaled", "stretched", "zoom", "centered", "wallpaper", "spanned", "none"]

    OPTION_LABELS = {
        "scaled": "option_scaled",
        "stretched": "option_stretched",
        "zoom": "option_zoom",
        "centered": "option_centered",
        "wallpaper": "option_wallpaper",
        "spanned": "option_spanned",
        "none": "option_none",
    }

    def __init__(self, main_win: MainWindow) -> None:
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        self.set_margin_top(12)
        self.set_margin_bottom(12)
        self.set_margin_start(12)
        self.set_margin_end(12)
        self.main_win = main_win
        self._build()

    def _build(self) -> None:
        group = Adw.PreferencesGroup(title=t("label_wallpaper"))
        self.append(group)

        option_row = Adw.ComboRow(title=t("label_scaling_option"))
        option_row.set_model(Gtk.StringList.new([t(k) for k in self.OPTION_LABELS.values()]))
        try:
            idx = self.OPTIONS.index(self.main_win.config.option)
        except ValueError:
            idx = 0
        option_row.set_selected(idx)
        self.option_row = option_row
        group.add(option_row)

        lang_group = Adw.PreferencesGroup(title=t("label_language"))
        self.append(lang_group)

        self.lang_row = Adw.ComboRow(title=t("label_language"))
        lang_options = ["English", "中文"]
        self.lang_row.set_model(Gtk.StringList.new(lang_options))
        self.lang_row.set_selected(0 if get_language() == "en" else 1)
        self.lang_row.connect("notify::selected", self._on_language_changed)
        lang_group.add(self.lang_row)

        tray_group = Adw.PreferencesGroup(title=t("label_system_tray"))
        self.append(tray_group)

        tray_row = Adw.ActionRow(title=t("label_minimize_tray"))
        self.tray_switch = Gtk.Switch()
        self.tray_switch.set_active(self.main_win.config.minimize_to_tray)
        self.tray_switch.set_valign(Gtk.Align.CENTER)
        self.tray_switch.connect("state-set", self._on_tray_toggle)
        tray_row.add_suffix(self.tray_switch)
        tray_group.add(tray_row)

        btn_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        btn_box.set_halign(Gtk.Align.END)
        self.append(btn_box)

        self.btn_apply = Gtk.Button(label=t("btn_apply"))
        self.btn_apply.add_css_class("suggested-action")
        self.btn_apply.connect("clicked", self._on_apply)
        btn_box.append(self.btn_apply)

        self.btn_reset = Gtk.Button(label=t("btn_reset"))
        self.btn_reset.connect("clicked", self._on_reset)
        btn_box.append(self.btn_reset)

    def _on_language_changed(self, _row: Adw.ComboRow, _pspec: object) -> None:
        lang = "zh" if self.lang_row.get_selected() == 1 else "en"
        set_language(lang)
        self.main_win.config.language = lang
        self.main_win.config.save()
        self.main_win.reload_ui()

    def _on_apply(self, _btn: Gtk.Button) -> None:
        idx = self.option_row.get_selected()
        self.main_win.config.option = self.OPTIONS[idx]
        self.main_win.config.save()

    def _on_reset(self, _btn: Gtk.Button) -> None:
        self.main_win.config = Config.default()
        self.option_row.set_selected(0)
        self.tray_switch.set_active(False)

    def _on_tray_toggle(self, _sw: Gtk.Switch, active: bool) -> None:
        self.main_win.config.minimize_to_tray = active
        self.main_win.config.save()

    def reload_ui(self) -> None:
        self.btn_apply.set_label(t("btn_apply"))
        self.btn_reset.set_label(t("btn_reset"))


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main() -> int:
    app = WallpaperChangerApp()
    return app.run(sys.argv)


if __name__ == "__main__":
    raise SystemExit(main())

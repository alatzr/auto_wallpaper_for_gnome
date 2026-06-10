"""Smoke tests for the GUI module.

These tests verify that the GUI classes can be instantiated without errors.
They do NOT require a display server (headless).
"""

from __future__ import annotations

import sys
from unittest.mock import MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

# We must initialise Gtk *before* any widget class is imported / constructed.
# The ``--help-gtk`` flag is harmless and lets us parse without actually
# starting the main loop.


def _init_gtk() -> None:
    """Initialise GTK runtime once."""
    import gi

    gi.require_version("Gtk", "4.0")
    gi.require_version("Adw", "1")
    from gi.repository import GLib, Gtk

    # Tiny trick: create a throwaway application so the default display is
    # initialised (works even in CI without a real display).
    try:
        app = Gtk.Application(application_id="com.github.wallpaper-changer.test")
        app.register(None)
    except Exception:
        pass


_init_gtk()

from gi.repository import Gtk

from wallpaper_changer.config import Config, MonitorConfig
from wallpaper_changer.gui import (
    MainWindow,
    PreviewTab,
    SettingsTab,
    SourceTab,
    SourceRow,
    TimerTab,
    WallpaperChangerApp,
)
from wallpaper_changer.monitor import Monitor


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_monitor(name: str = "DP-1", primary: bool = True) -> Monitor:
    return Monitor(name=name, width=2560, height=1440, x=0, y=0, is_primary=primary)


def _make_config(tmp_path) -> Config:
    return Config(
        interval=300,
        option="scaled",
        monitors=[MonitorConfig(name="DP-1", source_folder=str(tmp_path))],
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestWallpaperChangerApp:
    def test_instantiation(self):
        app = WallpaperChangerApp()
        assert app.get_application_id() == "com.github.wallpaper-changer"


class TestMainWindow:
    @patch("wallpaper_changer.gui.get_monitors", return_value=[])
    @patch("wallpaper_changer.gui.Config.load")
    def test_create_window(self, mock_load, mock_monkeys, tmp_path):
        mock_load.return_value = _make_config(tmp_path)
        app = Gtk.Application(application_id="test.main")
        app.register(None)
        win = MainWindow(application=app)
        assert win.get_title() == "Wallpaper Changer"


class TestPreviewTab:
    @patch("wallpaper_changer.gui.get_wallpaper", return_value="")
    def test_refresh_empty(self, mock_wp):
        app = Gtk.Application(application_id="test.preview")
        app.register(None)
        win = MainWindow(application=app)
        tab = PreviewTab(win)
        tab.refresh([_make_monitor()])


class TestSourceTab:
    def test_refresh(self, tmp_path):
        app = Gtk.Application(application_id="test.source")
        app.register(None)
        config = _make_config(tmp_path)
        win = MagicMock()
        win.config = config
        tab = SourceTab(win)
        tab.refresh([_make_monitor()], config)
        assert len(tab.rows) == 1


class TestSourceRow:
    def test_get_folder(self, tmp_path):
        row = SourceRow(_make_monitor(), str(tmp_path))
        assert row.get_folder() == str(tmp_path)


class TestTimerTab:
    @patch("wallpaper_changer.gui.is_service_installed", return_value=False)
    def test_create(self, mock_svc):
        app = Gtk.Application(application_id="test.timer")
        app.register(None)
        win = MagicMock()
        win.config = Config(interval=60, option="scaled", monitors=[])
        win.scheduler = MagicMock()
        tab = TimerTab(win)
        assert tab.spin.get_value() == 60


class TestSettingsTab:
    def test_create(self):
        app = Gtk.Application(application_id="test.settings")
        app.register(None)
        win = MagicMock()
        win.config = Config(interval=300, option="zoom", monitors=[])
        tab = SettingsTab(win)
        assert tab.option_row.get_selected() == tab.OPTIONS.index("zoom")


class TestSourceRowEdgeCases:
    def test_empty_folder(self):
        row = SourceRow(_make_monitor(), "")
        assert row.get_folder() == ""

    def test_unicode_folder(self, tmp_path):
        folder = tmp_path / "壁纸"
        folder.mkdir()
        row = SourceRow(_make_monitor(), str(folder))
        assert row.get_folder() == str(folder)

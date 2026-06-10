"""Tests for the monitor detection module."""

from __future__ import annotations

import textwrap
from unittest.mock import patch

import pytest

from wallpaper_changer.monitor import (
    Monitor,
    _parse_mutter_dbus_output,
    _parse_wlr_randr_output,
    _parse_xrandr_output,
    get_monitors,
)


class TestMonitorDataclass:
    def test_geometry(self):
        m = Monitor(name="DP-1", width=2560, height=1440, x=0, y=0, is_primary=True)
        assert m.geometry == "2560x1440+0+0"

    def test_geometry_with_offset(self):
        m = Monitor(name="HDMI-1", width=1920, height=1080, x=2560, y=100, is_primary=False)
        assert m.geometry == "1920x1080+2560+100"


class TestParseMutterDbusOutput:
    SAMPLE_OUTPUT = textwrap.dedent("""\
        (uint32 1, [(('DP-1', 'HKC', 'G24H2Classics', '0000000000001'), [('2560x1440@180.001', 2560, 1440, 180.00059509277344, 1.0, [1.0, 1.25], @a{sv} {}), ('2560x1440@144.000', 2560, 1440, 144.00047302246094, 1.0, [1.0, 1.25], {'is-current': <true>}), ('2560x1440@60.000', 2560, 1440, 60.000198364257812, 1.0, [1.0, 1.25], {'is-preferred': <true>})], {'is-builtin': <false>, 'display-name': <'HKC OVERSEAS LIMITED 24"'>}), (('DP-3', 'HKC', 'G24H2', '0000000000000'), [('2560x1440@179.998', 2560, 1440, 179.99810791015625, 1.0, [1.0, 1.25], {}), ('2560x1440@143.998', 2560, 1440, 143.99800109863281, 1.0, [1.0, 1.25], {'is-current': <true>})], {'is-builtin': <false>})], [(1152, 447, 1.25, uint32 0, true, [('DP-3', 'HKC', 'G24H2', '0000000000000')], @a{sv} {}), (0, 0, 1.25, 1, false, [('DP-1', 'HKC', 'G24H2Classics', '0000000000001')], {})], {'layout-mode': <uint32 1>})""")

    def test_parses_two_monitors(self):
        monitors = _parse_mutter_dbus_output(self.SAMPLE_OUTPUT)
        assert monitors is not None
        assert len(monitors) == 2

    def test_dp1_resolution(self):
        monitors = _parse_mutter_dbus_output(self.SAMPLE_OUTPUT)
        dp1 = next(m for m in monitors if m.name == "DP-1")
        assert dp1.width == 2560
        assert dp1.height == 1440

    def test_dp3_resolution(self):
        monitors = _parse_mutter_dbus_output(self.SAMPLE_OUTPUT)
        dp3 = next(m for m in monitors if m.name == "DP-3")
        assert dp3.width == 2560
        assert dp3.height == 1440

    def test_dp1_position(self):
        monitors = _parse_mutter_dbus_output(self.SAMPLE_OUTPUT)
        dp1 = next(m for m in monitors if m.name == "DP-1")
        assert dp1.x == 0
        assert dp1.y == 0

    def test_dp3_position(self):
        monitors = _parse_mutter_dbus_output(self.SAMPLE_OUTPUT)
        dp3 = next(m for m in monitors if m.name == "DP-3")
        assert dp3.x == 1152
        assert dp3.y == 447

    def test_primary_monitor(self):
        monitors = _parse_mutter_dbus_output(self.SAMPLE_OUTPUT)
        dp1 = next(m for m in monitors if m.name == "DP-1")
        dp3 = next(m for m in monitors if m.name == "DP-3")
        assert dp1.is_primary is False
        assert dp3.is_primary is True

    def test_real_gdbus_output(self):
        """Test with the actual output captured from this system."""
        real_output = (
            "(uint32 1, [(('DP-1', 'HKC', 'G24H2Classics', '0000000000001'), "
            "[('2560x1440@180.001', 2560, 1440, 180.00059509277344, 1.0, "
            "[1.0, 1.25, 1.3333333730697632, 1.6666666269302368, 2.0, 2.5, 2.6666667461395264], "
            "@a{sv} {}), ('2560x1440@144.000', 2560, 1440, 144.00047302246094, 1.0, "
            "[1.0, 1.25, 1.3333333730697632, 1.6666666269302368, 2.0, 2.5, 2.6666667461395264], "
            "{'is-current': <true>}), ('2560x1440@60.000', 2560, 1440, 60.000198364257812, 1.0, "
            "[1.0, 1.25, 1.3333333730697632, 1.6666666269302368, 2.0, 2.5, 2.6666667461395264], "
            "{'is-preferred': <true>})], {'is-builtin': <false>, 'display-name': <'HKC OVERSEAS LIMITED 24\"'>}), "
            "(('DP-3', 'HKC', 'G24H2', '0000000000000'), [('2560x1440@179.998', 2560, 1440, 179.99810791015625, 1.0, "
            "[1.0, 1.25, 1.3333333730697632, 1.6666666269302368, 2.0, 2.5, 2.6666667461395264], {}), "
            "('2560x1440@143.998', 2560, 1440, 143.99800109863281, 1.0, "
            "[1.0, 1.25, 1.3333333730697632, 1.6666666269302368, 2.0, 2.5, 2.6666667461395264], "
            "{'is-current': <true>})], {'is-builtin': <false>})], "
            "[(1152, 447, 1.25, uint32 0, true, [('DP-3', 'HKC', 'G24H2', '0000000000000')], @a{sv} {}), "
            "(0, 0, 1.25, 1, false, [('DP-1', 'HKC', 'G24H2Classics', '0000000000001')], {})], "
            "{'layout-mode': <uint32 1>, 'supports-changing-layout-mode': <true>})"
        )
        monitors = _parse_mutter_dbus_output(real_output)
        assert monitors is not None
        assert len(monitors) == 2
        names = {m.name for m in monitors}
        assert names == {"DP-1", "DP-3"}
        for m in monitors:
            assert m.width == 2560
            assert m.height == 1440


class TestParseWlrRandrOutput:
    SAMPLE_OUTPUT = textwrap.dedent("""\
        DP-1 "HKC G24H2Classics (DP-1)"
          Physical size: 530x300 mm
          Enabled: yes
          Modes:
            2560x1440 px, 144.000 Hz (preferred, current)
            1920x1080 px, 60.000 Hz
          Position: 0,0
          Transform: normal
          Scale: 1.00
          Adaptive Sync: disabled
        HDMI-1 "Samsung TV (HDMI-1)"
          Physical size: 1200x675 mm
          Enabled: yes
          Modes:
            1920x1080 px, 60.000 Hz (preferred, current)
          Position: 2560,0
          Transform: normal
          Scale: 1.00
    """)

    def test_parses_two_monitors(self):
        monitors = _parse_wlr_randr_output(self.SAMPLE_OUTPUT)
        assert monitors is not None
        assert len(monitors) == 2

    def test_dp1_properties(self):
        monitors = _parse_wlr_randr_output(self.SAMPLE_OUTPUT)
        dp1 = monitors[0]
        assert dp1.name == "DP-1"
        assert dp1.width == 2560
        assert dp1.height == 1440
        assert dp1.x == 0
        assert dp1.y == 0
        assert dp1.is_primary is True

    def test_hdmi1_properties(self):
        monitors = _parse_wlr_randr_output(self.SAMPLE_OUTPUT)
        hdmi1 = monitors[1]
        assert hdmi1.name == "HDMI-1"
        assert hdmi1.width == 1920
        assert hdmi1.height == 1080
        assert hdmi1.x == 2560
        assert hdmi1.y == 0
        assert hdmi1.is_primary is False


class TestParseXrandrOutput:
    SAMPLE_OUTPUT = textwrap.dedent("""\
        Screen 0: minimum 320 x 200, current 4480 x 1440, maximum 16384 x 16384
        DP-1 connected primary 2560x1440+0+0 (normal left inverted right x axis y axis) 530mm x 300mm
           2560x1440     144.00*+  60.00
           1920x1080     120.00    60.00
        HDMI-1 connected 1920x1080+2560+0 (normal left inverted right x axis y axis) 1200mm x 675mm
           1920x1080     60.00*+
        DP-2 disconnected (normal left inverted right x axis y axis)
    """)

    def test_parses_two_monitors(self):
        monitors = _parse_xrandr_output(self.SAMPLE_OUTPUT)
        assert monitors is not None
        assert len(monitors) == 2

    def test_dp1_properties(self):
        monitors = _parse_xrandr_output(self.SAMPLE_OUTPUT)
        dp1 = next(m for m in monitors if m.name == "DP-1")
        assert dp1.width == 2560
        assert dp1.height == 1440
        assert dp1.x == 0
        assert dp1.y == 0
        assert dp1.is_primary is True

    def test_hdmi1_properties(self):
        monitors = _parse_xrandr_output(self.SAMPLE_OUTPUT)
        hdmi1 = next(m for m in monitors if m.name == "HDMI-1")
        assert hdmi1.width == 1920
        assert hdmi1.height == 1080
        assert hdmi1.x == 2560
        assert hdmi1.y == 0
        assert hdmi1.is_primary is False

    def test_disconnected_ignored(self):
        monitors = _parse_xrandr_output(self.SAMPLE_OUTPUT)
        names = {m.name for m in monitors}
        assert "DP-2" not in names


class TestGetMonitors:
    def test_returns_monitors_on_live_system(self):
        """Integration test: runs on the actual system."""
        monitors = get_monitors()
        assert len(monitors) > 0
        for m in monitors:
            assert isinstance(m, Monitor)
            assert m.width > 0
            assert m.height > 0
            assert isinstance(m.name, str)
            assert len(m.name) > 0

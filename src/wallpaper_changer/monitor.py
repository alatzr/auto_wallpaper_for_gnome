"""Monitor detection module for Linux.

Supports GNOME Wayland (via Mutter D-Bus) and X11 (via xrandr).
"""

from __future__ import annotations

import json
import re
import subprocess
from dataclasses import dataclass
from typing import Callable


@dataclass
class Monitor:
    """Represents a connected display monitor."""

    name: str
    width: int
    height: int
    x: int
    y: int
    is_primary: bool
    rotation: int = 0  # 0=normal, 1=90°, 2=180°, 3=270°
    scaling: float = 1.0

    @property
    def geometry(self) -> str:
        """Return geometry string like '2560x1440+0+0'."""
        return f"{self.width}x{self.height}+{self.x}+{self.y}"


def get_monitors() -> list[Monitor]:
    """Get list of connected monitors with their resolutions and positions.

    Tries detection methods in order:
    1. GNOME Mutter D-Bus (Wayland)
    2. xrandr (X11)
    """
    for detector in _get_detectors():
        try:
            monitors = detector()
            if monitors:
                return monitors
        except (subprocess.CalledProcessError, FileNotFoundError, Exception):
            continue
    raise RuntimeError(
        "No supported monitor detection method found. "
        "Ensure you are running GNOME Wayland or have xrandr installed for X11."
    )


def _get_detectors() -> list[Callable[[], list[Monitor] | None]]:
    """Return list of detector functions to try."""
    return [
        _detect_gnome_dbus,
        _detect_wlr_randr,
        _detect_xrandr,
    ]


# ---------------------------------------------------------------------------
# GNOME Mutter D-Bus detection (Wayland)
# ---------------------------------------------------------------------------

def _detect_gnome_dbus() -> list[Monitor] | None:
    """Detect monitors via GNOME Mutter DisplayConfig D-Bus interface."""
    output = subprocess.check_output(
        [
            "gdbus", "call", "--session",
            "--dest", "org.gnome.Mutter.DisplayConfig",
            "--object-path", "/org/gnome/Mutter/DisplayConfig",
            "--method", "org.gnome.Mutter.DisplayConfig.GetCurrentState",
        ],
        text=True,
    )
    return _parse_mutter_dbus_output(output)


def _parse_mutter_dbus_output(output: str) -> list[Monitor] | None:
    """Parse Mutter DisplayConfig.GetCurrentState output.

    The output has the structure:
      (uint32, [monitors...], [logical_monitors...], {global_props})

    monitors: ((name, vendor, product, serial), [modes...], {props})
    logical_monitors: (x, y, scale, transform, primary, [(name, vendor, product, serial)], {})
    """
    monitors_info = _extract_monitors(output)
    logical_info = _extract_logical_monitors(output)

    if not monitors_info:
        return None

    result = []
    for lm in logical_info:
        lm_x, lm_y, lm_scale, lm_transform, lm_primary, lm_connector = lm
        rotation = lm_transform % 4  # ignore flip bits (4-7), keep rotation (0-3)
        for mi in monitors_info:
            mi_name, mi_width, mi_height = mi
            if mi_name == lm_connector:
                w, h = mi_width, mi_height
                if rotation in (1, 3):  # 90° or 270°
                    w, h = h, w
                result.append(
                    Monitor(
                        name=mi_name,
                        width=w,
                        height=h,
                        x=lm_x,
                        y=lm_y,
                        is_primary=lm_primary,
                        rotation=rotation,
                        scaling=lm_scale,
                    )
                )
                break
        else:
            result.append(
                Monitor(
                    name=lm_connector,
                    width=0,
                    height=0,
                    x=lm_x,
                    y=lm_y,
                    is_primary=lm_primary,
                    rotation=rotation,
                    scaling=lm_scale,
                )
            )

    return result if result else None


def _extract_monitors(output: str) -> list[tuple[str, int, int]]:
    """Extract (connector_name, current_width, current_height) from monitors array.

    Looks for patterns like: (('DP-1', ...), [('2560x1440@144.000', 2560, 1440, ...), ...], ...)
    where the mode has 'is-current': <true>.
    """
    results = []

    monitor_pattern = re.compile(
        r"\(\('([^']+)',\s*'[^']*',\s*'[^']*',\s*'[^']*'\),\s*\["
    )
    mode_pattern = re.compile(
        r"\('(\d+)x(\d+)@[^']+',\s*(\d+),\s*(\d+),[^)]*\)"
    )

    blocks = output.split(")], {")
    for i, block in enumerate(blocks[:-1]):
        m = monitor_pattern.search(block)
        if not m:
            continue
        connector = m.group(1)

        current_mode = None
        preferred_fallback = None
        first_mode = None

        for mm in mode_pattern.finditer(block):
            w, h = int(mm.group(3)), int(mm.group(4))
            mode_text = mm.group(0)
            if first_mode is None:
                first_mode = (w, h)
            if "is-preferred" in mode_text:
                preferred_fallback = (w, h)
            if "is-current" in mode_text:
                current_mode = (w, h)
                break

        chosen = current_mode or preferred_fallback or first_mode
        if chosen:
            results.append((connector, chosen[0], chosen[1]))

    return results


def _extract_logical_monitors(output: str) -> list[tuple[int, int, float, int, bool, str]]:
    """Extract logical monitor layout: (x, y, scale, transform, is_primary, connector_name)."""
    results = []

    lm_pattern = re.compile(
        r"\((\d+),\s*(\d+),\s*([\d.]+),\s*(?:uint32\s+)?(\d+),\s*(true|false),\s*\[\("
        r"'([^']+)',"
    )
    for m in lm_pattern.finditer(output):
        x = int(m.group(1))
        y = int(m.group(2))
        scale = float(m.group(3))
        transform = int(m.group(4))
        primary = m.group(5) == "true"
        connector = m.group(6)
        results.append((x, y, scale, transform, primary, connector))

    return results


# ---------------------------------------------------------------------------
# wlr-randr detection (wlroots Wayland compositors)
# ---------------------------------------------------------------------------

def _detect_wlr_randr() -> list[Monitor] | None:
    """Detect monitors via wlr-randr."""
    output = subprocess.check_output(["wlr-randr"], text=True)
    return _parse_wlr_randr_output(output)


def _parse_wlr_randr_output(output: str) -> list[Monitor] | None:
    """Parse wlr-randr output.

    Example output:
        DP-1 "HKC G24H2Classics (DP-1)"
          Physical size: 530x300 mm
          Enabled: yes
          Modes:
            2560x1440 px, 144.000 Hz (preferred, current)
          Position: 0,0
          Transform: normal
          Scale: 1.00
          Adaptive Sync: disabled
    """
    monitors: list[Monitor] = []
    current_name: str | None = None
    current_width = 0
    current_height = 0
    current_x = 0
    current_y = 0
    current_scale = 1.0

    for line in output.splitlines():
        line_stripped = line.strip()

        monitor_match = re.match(r"^(\S+)\s+", line)
        if monitor_match and not line.startswith(" "):
            if current_name and current_width and current_height:
                monitors.append(
                    Monitor(
                        name=current_name,
                        width=current_width,
                        height=current_height,
                        x=current_x,
                        y=current_y,
                        is_primary=len(monitors) == 0,
                        scaling=current_scale,
                    )
                )
            current_name = monitor_match.group(1)
            current_width = current_height = current_x = current_y = 0
            current_scale = 1.0

        mode_match = re.match(r"\s+(\d+)x(\d+)\s+px,.*current", line)
        if mode_match:
            current_width = int(mode_match.group(1))
            current_height = int(mode_match.group(2))

        pos_match = re.match(r"^\s*Position:\s*(\d+),(\d+)", line_stripped)
        if pos_match:
            current_x = int(pos_match.group(1))
            current_y = int(pos_match.group(2))

        scale_match = re.match(r"^\s*Scale:\s*([\d.]+)", line_stripped)
        if scale_match:
            current_scale = float(scale_match.group(1))

    if current_name and current_width and current_height:
        monitors.append(
            Monitor(
                name=current_name,
                width=current_width,
                height=current_height,
                x=current_x,
                y=current_y,
                is_primary=len(monitors) == 0,
                scaling=current_scale,
            )
        )

    return monitors if monitors else None


# ---------------------------------------------------------------------------
# xrandr detection (X11)
# ---------------------------------------------------------------------------

def _detect_xrandr() -> list[Monitor] | None:
    """Detect monitors via xrandr."""
    output = subprocess.check_output(["xrandr", "--query"], text=True)
    return _parse_xrandr_output(output)


def _parse_xrandr_output(output: str) -> list[Monitor] | None:
    """Parse xrandr --query output.

    Example lines:
        DP-1 connected primary 2560x1440+0+0 ...
        HDMI-1 connected 1920x1080+2560+0 ...
    """
    monitors: list[Monitor] = []
    pattern = re.compile(
        r"^(\S+)\s+connected\s+(primary\s+)?(\d+)x(\d+)\+(\d+)\+(\d+)"
    )
    for line in output.splitlines():
        m = pattern.match(line)
        if m:
            monitors.append(
                Monitor(
                    name=m.group(1),
                    width=int(m.group(3)),
                    height=int(m.group(4)),
                    x=int(m.group(5)),
                    y=int(m.group(6)),
                    is_primary=m.group(2) is not None,
                )
            )

    return monitors if monitors else None

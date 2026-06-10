"""Integration tests for the full wallpaper-changer pipeline."""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest
from PIL import Image

from wallpaper_changer.monitor import get_monitors, Monitor
from wallpaper_changer.source import WallpaperSource
from wallpaper_changer.wallpaper import set_wallpaper, compose_multi_monitor_wallpaper, get_wallpaper


@pytest.fixture
def test_wallpaper_dir(tmp_path: Path) -> Path:
    """Create a directory with real test wallpaper images."""
    d = tmp_path / "wallpapers"
    d.mkdir()
    colors = ["red", "green", "blue", "yellow", "purple"]
    for i, color in enumerate(colors):
        img = Image.new("RGB", (1920, 1080), color=color)
        img.save(d / f"wallpaper_{i}.png")
    return d


class TestIntegrationMonitorDetection:
    """Test monitor detection on the live system."""

    def test_detects_at_least_one_monitor(self):
        monitors = get_monitors()
        assert len(monitors) >= 1

    def test_monitor_properties(self):
        monitors = get_monitors()
        for m in monitors:
            assert isinstance(m, Monitor)
            assert m.width > 0
            assert m.height > 0
            assert len(m.name) > 0

    def test_has_primary_monitor(self):
        monitors = get_monitors()
        primaries = [m for m in monitors if m.is_primary]
        assert len(primaries) == 1


class TestIntegrationSourceSelection:
    """Test wallpaper source detection and random selection."""

    def test_get_images_from_test_folder(self, test_wallpaper_dir: Path):
        src = WallpaperSource(str(test_wallpaper_dir))
        images = src.get_images()
        assert len(images) == 5

    def test_random_image_from_test_folder(self, test_wallpaper_dir: Path):
        src = WallpaperSource(str(test_wallpaper_dir))
        img = src.get_random_image()
        assert img is not None
        assert img.exists()
        assert img.suffix == ".png"

    def test_random_image_avoids_recent(self, test_wallpaper_dir: Path):
        src = WallpaperSource(str(test_wallpaper_dir))
        results = set()
        for _ in range(5):
            img = src.get_random_image(avoid_recent=4)
            assert img is not None
            results.add(str(img))
        assert len(results) == 5


class TestIntegrationComposeMultiMonitor:
    """Test multi-monitor wallpaper composition."""

    def test_compose_for_two_monitors(self, test_wallpaper_dir: Path):
        src = WallpaperSource(str(test_wallpaper_dir))
        img1 = src.get_random_image()
        img2 = src.get_random_image()
        assert img1 is not None
        assert img2 is not None

        monitors = [
            Monitor(name="DP-1", width=2560, height=1440, x=0, y=0, is_primary=True),
            Monitor(name="HDMI-1", width=1920, height=1080, x=2560, y=0, is_primary=False),
        ]

        images = [
            (str(img1), monitors[0].width, monitors[0].height),
            (str(img2), monitors[1].width, monitors[1].height),
        ]
        layout = [(m.x, m.y) for m in monitors]

        result = compose_multi_monitor_wallpaper(images, layout)
        assert Path(result).exists()

        composed = Image.open(result)
        assert composed.size == (4480, 1440)

        import os
        os.unlink(result)

    def test_compose_single_monitor(self, test_wallpaper_dir: Path):
        src = WallpaperSource(str(test_wallpaper_dir))
        img = src.get_random_image()
        assert img is not None

        images = [(str(img), 2560, 1440)]
        layout = [(0, 0)]

        result = compose_multi_monitor_wallpaper(images, layout)
        assert Path(result).exists()

        composed = Image.open(result)
        assert composed.size == (2560, 1440)

        import os
        os.unlink(result)


class TestIntegrationSetWallpaper:
    """Test setting wallpaper on the live system."""

    def test_set_wallpaper_from_test_folder(self, test_wallpaper_dir: Path):
        src = WallpaperSource(str(test_wallpaper_dir))
        img = src.get_random_image()
        assert img is not None

        result = set_wallpaper(str(img), "scaled")
        assert result is True

    def test_get_wallpaper_returns_path(self):
        result = get_wallpaper()
        assert isinstance(result, str)
        assert len(result) > 0

    def test_wallpaper_persists_after_set(self, test_wallpaper_dir: Path):
        src = WallpaperSource(str(test_wallpaper_dir))
        img = src.get_random_image()
        assert img is not None

        set_wallpaper(str(img), "scaled")
        current = get_wallpaper()
        assert img.name in current


class TestIntegrationFullPipeline:
    """End-to-end integration test: detect -> select -> compose -> set."""

    def test_full_pipeline_single_monitor(self, test_wallpaper_dir: Path):
        monitors = get_monitors()
        assert len(monitors) >= 1

        src = WallpaperSource(str(test_wallpaper_dir))
        img = src.get_random_image()
        assert img is not None

        result = set_wallpaper(str(img), "scaled")
        assert result is True

        current = get_wallpaper()
        assert img.name in current

    def test_full_pipeline_multi_monitor(self, test_wallpaper_dir: Path):
        monitors = get_monitors()
        assert len(monitors) >= 1

        src = WallpaperSource(str(test_wallpaper_dir))
        images = []
        for m in monitors:
            img = src.get_random_image()
            assert img is not None
            images.append((str(img), m.width, m.height))

        layout = [(m.x, m.y) for m in monitors]

        if len(monitors) > 1:
            composed = compose_multi_monitor_wallpaper(images, layout)
            assert Path(composed).exists()
            result = set_wallpaper(composed, "scaled")
            assert result is True
            import os
            os.unlink(composed)
        else:
            result = set_wallpaper(images[0][0], "scaled")
            assert result is True

"""Tests for the wallpaper source module."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from wallpaper_changer.source import IMAGE_EXTENSIONS, WallpaperSource


@pytest.fixture
def image_dir(tmp_path: Path) -> Path:
    """Create a temp directory with sample image files."""
    d = tmp_path / "wallpapers"
    d.mkdir()
    for i, ext in enumerate(sorted(IMAGE_EXTENSIONS)):
        (d / f"img{i}{ext}").write_bytes(b"\x00")
    (d / "readme.txt").write_text("not an image")
    sub = d / "subfolder"
    sub.mkdir()
    (sub / "nested.jpg").write_bytes(b"\x00")
    return d


@pytest.fixture
def empty_dir(tmp_path: Path) -> Path:
    """Create an empty temp directory."""
    d = tmp_path / "empty"
    d.mkdir()
    return d


@pytest.fixture
def history_file(tmp_path: Path) -> Path:
    return tmp_path / "history.json"


class TestGetImages:
    def test_returns_all_image_types(self, image_dir: Path):
        src = WallpaperSource(str(image_dir))
        images = src.get_images()
        names = {p.name for p in images}
        assert "img0.bmp" in names
        assert "img1.gif" in names
        assert "img2.jpeg" in names
        assert "img3.jpg" in names
        assert "img4.png" in names
        assert "img5.webp" in names

    def test_excludes_non_image_files(self, image_dir: Path):
        src = WallpaperSource(str(image_dir))
        images = src.get_images()
        names = {p.name for p in images}
        assert "readme.txt" not in names

    def test_includes_subfolder_images(self, image_dir: Path):
        src = WallpaperSource(str(image_dir))
        images = src.get_images()
        names = {p.name for p in images}
        assert "nested.jpg" in names

    def test_empty_folder(self, empty_dir: Path):
        src = WallpaperSource(str(empty_dir))
        assert src.get_images() == []

    def test_nonexistent_folder(self, tmp_path: Path):
        src = WallpaperSource(str(tmp_path / "does_not_exist"))
        assert src.get_images() == []

    def test_sorted_output(self, image_dir: Path):
        src = WallpaperSource(str(image_dir))
        images = src.get_images()
        assert images == sorted(images)


class TestGetRandomImage:
    def test_returns_path(self, image_dir: Path):
        src = WallpaperSource(str(image_dir))
        img = src.get_random_image()
        assert img is not None
        assert img.is_file()
        assert img.suffix.lower() in IMAGE_EXTENSIONS

    def test_none_when_empty(self, empty_dir: Path):
        src = WallpaperSource(str(empty_dir))
        assert src.get_random_image() is None

    def test_avoids_recent(self, image_dir: Path):
        src = WallpaperSource(str(image_dir))
        total = len(src.get_images())
        results = set()
        for _ in range(total):
            img = src.get_random_image(avoid_recent=total - 1)
            assert img is not None
            results.add(str(img))
        assert len(results) == total

    def test_history_grows(self, image_dir: Path):
        src = WallpaperSource(str(image_dir))
        src.get_random_image()
        src.get_random_image()
        assert len(src.history) == 2

    def test_avoid_recent_fallback(self, image_dir: Path):
        src = WallpaperSource(str(image_dir))
        images = src.get_images()
        for img in images:
            src.history.append(str(img))
        result = src.get_random_image(avoid_recent=len(images))
        assert result is not None


class TestHistoryPersistence:
    def test_save_and_load(self, image_dir: Path, history_file: Path):
        src = WallpaperSource(str(image_dir), history_file=str(history_file))
        img = src.get_random_image()
        assert img is not None

        src2 = WallpaperSource(str(image_dir), history_file=str(history_file))
        assert src2.history == [str(img)]

    def test_clear_history(self, image_dir: Path, history_file: Path):
        src = WallpaperSource(str(image_dir), history_file=str(history_file))
        src.get_random_image()
        assert len(src.history) == 1

        src.clear_history()
        assert src.history == []
        assert json.loads(history_file.read_text()) == []

    def test_corrupted_history_file(self, image_dir: Path, history_file: Path):
        history_file.write_text("not valid json{{{")
        src = WallpaperSource(str(image_dir), history_file=str(history_file))
        assert src.history == []

    def test_no_history_file(self, image_dir: Path):
        src = WallpaperSource(str(image_dir))
        src.get_random_image()
        assert len(src.history) == 1
        src._load_history()
        assert src.history == [src.history[0]]

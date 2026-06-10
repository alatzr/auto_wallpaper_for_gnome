import pytest
import os
import tempfile
from pathlib import Path
from PIL import Image

from wallpaper_changer.wallpaper import (
    set_wallpaper,
    get_wallpaper,
    path_to_uri,
    uri_to_path,
    compose_multi_monitor_wallpaper
)


@pytest.fixture
def sample_image():
    """Create a temporary test image."""
    with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as f:
        img = Image.new('RGB', (1920, 1080), color='blue')
        img.save(f, 'PNG')
        yield f.name
    os.unlink(f.name)


@pytest.fixture
def sample_images():
    """Create multiple temporary test images."""
    paths = []
    for i in range(2):
        with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as f:
            img = Image.new('RGB', (1920, 1080), color=['red', 'green'][i])
            img.save(f, 'PNG')
            paths.append(f.name)
    yield paths
    for p in paths:
        os.unlink(p)


class TestPathToUri:
    def test_simple_path(self):
        assert path_to_uri('/home/user/image.png') == 'file:///home/user/image.png'

    def test_path_with_spaces(self):
        assert path_to_uri('/home/user/my image.png') == 'file:///home/user/my%20image.png'

    def test_path_with_special_chars(self):
        assert path_to_uri('/home/user/image (1).png') == 'file:///home/user/image%20%281%29.png'

    def test_relative_path_becomes_absolute(self):
        result = path_to_uri('image.png')
        assert result.startswith('file://')
        assert 'image.png' in result


class TestUriToPath:
    def test_simple_uri(self):
        assert uri_to_path('file:///home/user/image.png') == '/home/user/image.png'

    def test_encoded_uri(self):
        assert uri_to_path('file:///home/user/my%20image.png') == '/home/user/my image.png'

    def test_non_file_uri(self):
        assert uri_to_path('/home/user/image.png') == '/home/user/image.png'


class TestComposeMultiMonitorWallpaper:
    def test_compose_two_monitors(self, sample_images):
        images = [
            (sample_images[0], 1920, 1080),
            (sample_images[1], 1920, 1080)
        ]
        layout = [(0, 0), (1920, 0)]

        result = compose_multi_monitor_wallpaper(images, layout)

        assert os.path.exists(result)
        img = Image.open(result)
        assert img.size == (3840, 1080)
        os.unlink(result)

    def test_compose_stacked_monitors(self, sample_images):
        images = [
            (sample_images[0], 1920, 1080),
            (sample_images[1], 1920, 1080)
        ]
        layout = [(0, 0), (0, 1080)]

        result = compose_multi_monitor_wallpaper(images, layout)

        assert os.path.exists(result)
        img = Image.open(result)
        assert img.size == (1920, 2160)
        os.unlink(result)

    def test_mismatched_lengths_raises(self, sample_images):
        images = [(sample_images[0], 1920, 1080)]
        layout = [(0, 0), (1920, 0)]

        with pytest.raises(ValueError, match="Number of images must match"):
            compose_multi_monitor_wallpaper(images, layout)

    def test_different_resolutions(self, sample_images):
        images = [
            (sample_images[0], 2560, 1440),
            (sample_images[1], 1920, 1080)
        ]
        layout = [(0, 0), (2560, 0)]

        result = compose_multi_monitor_wallpaper(images, layout)

        img = Image.open(result)
        assert img.size == (4480, 1440)
        os.unlink(result)


class TestSetWallpaper:
    def test_invalid_file_returns_false(self):
        assert set_wallpaper('/nonexistent/image.png') is False

    def test_sets_wallpaper(self, sample_image):
        result = set_wallpaper(sample_image, 'scaled')
        assert result is True

    def test_wallpaper_was_set(self, sample_image):
        set_wallpaper(sample_image, 'zoom')
        current = get_wallpaper()
        assert 'sample' in current or Path(sample_image).name in current


class TestGetWallpaper:
    def test_returns_string(self):
        result = get_wallpaper()
        assert isinstance(result, str)

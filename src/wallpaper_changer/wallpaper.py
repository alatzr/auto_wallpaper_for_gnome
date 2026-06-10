import subprocess
import os
import urllib.parse
from pathlib import Path
from PIL import Image
from PIL.ImageOps import fit as image_fit


def set_wallpaper(image_path: str, option: str = 'scaled') -> bool:
    """Set wallpaper for GNOME desktop.

    Args:
        image_path: Path to the image file
        option: Wallpaper scaling option. Options include:
            - 'scaled': Scale to fit (default)
            - 'stretched': Stretch to fill
            - 'zoom': Zoom to fill
            - 'centered': Center without scaling
            - 'wallpaper': Tile the image
            - 'spanned': Span across all monitors
            - 'none': No scaling

    Returns:
        True if successful, False otherwise
    """
    try:
        abs_path = Path(image_path).resolve()
        if not abs_path.exists():
            raise FileNotFoundError(f"Image file not found: {abs_path}")

        file_uri = path_to_uri(str(abs_path))

        subprocess.run(
            ['gsettings', 'set', 'org.gnome.desktop.background', 'picture-uri', file_uri],
            check=True,
            capture_output=True
        )

        subprocess.run(
            ['gsettings', 'set', 'org.gnome.desktop.background', 'picture-uri-dark', file_uri],
            check=True,
            capture_output=True
        )

        subprocess.run(
            ['gsettings', 'set', 'org.gnome.desktop.background', 'picture-options', option],
            check=True,
            capture_output=True
        )

        return True

    except (subprocess.CalledProcessError, FileNotFoundError) as e:
        print(f"Error setting wallpaper: {e}")
        return False


def get_wallpaper() -> str:
    """Get current wallpaper path.

    Returns:
        Path to current wallpaper image, or empty string if not set
    """
    try:
        result = subprocess.run(
            ['gsettings', 'get', 'org.gnome.desktop.background', 'picture-uri'],
            capture_output=True,
            text=True,
            check=True
        )
        uri = result.stdout.strip().strip("'")
        return uri_to_path(uri)
    except subprocess.CalledProcessError:
        return ""


def path_to_uri(path: str) -> str:
    """Convert a file path to a file:// URI.

    Args:
        path: Absolute file path

    Returns:
        file:// URI string
    """
    abs_path = Path(path).resolve()
    return 'file://' + urllib.parse.quote(str(abs_path), safe='/:@')


def uri_to_path(uri: str) -> str:
    """Convert a file:// URI to a file path.

    Args:
        uri: file:// URI string

    Returns:
        File path string
    """
    if uri.startswith('file://'):
        return urllib.parse.unquote(uri[7:])
    return uri


def compose_multi_monitor_wallpaper(
    images: list[tuple[str, int, int]],
    layout: list[tuple[int, int]],
    mode: str = 'zoom',
    scaling: float = 1.0,
) -> str:
    """Compose multiple images into one for multi-monitor setup.

    GNOME's 'spanned' mode maps the wallpaper image proportionally to the
    logical desktop. Positions from Mutter are already in logical coordinates,
    and monitor sizes from Mutter are physical pixels. We must convert sizes
    to logical (divide by scaling) so the composed image dimensions match the
    logical desktop exactly. A quality multiplier is applied for sharpness.

    Args:
        images: List of (image_path, target_width, target_height) for each monitor
               (width/height in physical pixels from Mutter)
        layout: List of (x_offset, y_offset) for each monitor position
               (already in logical coordinates from Mutter)
        mode: Wallpaper scaling mode (zoom, scaled, stretched, centered, spanned)
        scaling: Monitor scaling factor

    Returns:
        Path to composed image saved in /tmp
    """
    if len(images) != len(layout):
        raise ValueError("Number of images must match number of layout positions")

    # Quality multiplier: compose at higher resolution for sharpness
    quality = 2

    # Convert physical sizes to logical, then apply quality multiplier
    logical_images = []
    for (image_path, target_w, target_h) in images:
        log_w = int(target_w / scaling) * quality
        log_h = int(target_h / scaling) * quality
        logical_images.append((image_path, log_w, log_h))

    # Layout offsets are already logical, apply quality multiplier
    logical_layout = [(x * quality, y * quality) for (x, y) in layout]

    # Canvas size matches logical desktop * quality
    total_width = max(x + w for (x, _), (_, w, _) in zip(logical_layout, logical_images))
    total_height = max(y + h for (_, y), (_, _, h) in zip(logical_layout, logical_images))

    canvas = Image.new('RGB', (total_width, total_height), color='black')

    for (image_path, target_w, target_h), (x_offset, y_offset) in zip(logical_images, logical_layout):
        img = Image.open(image_path).convert('RGB')

        if mode == 'zoom':
            img = image_fit(img, (target_w, target_h), method=Image.LANCZOS, centering=(0.5, 0.5))
        elif mode == 'scaled':
            img.thumbnail((target_w, target_h), Image.LANCZOS)
            bg = Image.new('RGB', (target_w, target_h), color='black')
            offset_x = (target_w - img.width) // 2
            offset_y = (target_h - img.height) // 2
            bg.paste(img, (offset_x, offset_y))
            img = bg
        elif mode == 'stretched':
            img = img.resize((target_w, target_h), Image.LANCZOS)
        elif mode == 'centered':
            bg = Image.new('RGB', (target_w, target_h), color='black')
            offset_x = (target_w - img.width) // 2
            offset_y = (target_h - img.height) // 2
            bg.paste(img, (min(offset_x, 0), min(offset_y, 0)))
            img = bg
        else:
            img = img.resize((target_w, target_h), Image.LANCZOS)

        canvas.paste(img, (x_offset, y_offset))
        img.close()

    cache_dir = Path.home() / '.cache' / 'wallpaper-changer'
    cache_dir.mkdir(parents=True, exist_ok=True)
    output_path = str(cache_dir / 'composed_wallpaper.png')
    canvas.save(output_path, 'PNG')
    return output_path

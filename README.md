# Wallpaper Changer

Automatic wallpaper rotation for **Fedora 43 (GNOME Wayland)** with multi-monitor support. Each monitor can display a different wallpaper sourced from its own folder, composited into a single image and applied via GNOME's native `gsettings`.

## Features

- **Multi-monitor support** — assign independent source folders per monitor; images are composited into a single wallpaper
- **Automatic rotation** — configurable interval (default: 300s / 5 min)
- **Random selection** — avoids recently shown wallpapers
- **Systemd integration** — install as a user service for automatic startup
- **CLI interface** — 9 subcommands for full control
- **Native GNOME** — uses `gsettings`, works on Wayland and X11

## Installation

### Prerequisites

- Python 3.11+
- Fedora 43 with GNOME (Wayland or X11)
- `Pillow` (image processing)

### Install from source

```bash
git clone <repo-url> wallpaper_changer
cd wallpaper_changer
pip install -e .
```

### Install systemd service

```bash
wallpaper-changer install
systemctl --user enable wallpaper-changer
systemctl --user start wallpaper-changer
```

## Usage

### CLI Commands

| Command | Description |
|---------|-------------|
| `wallpaper-changer start` | Start automatic rotation (foreground, Ctrl+C to stop) |
| `wallpaper-changer stop` | Stop automatic rotation |
| `wallpaper-changer next` | Immediately switch to next wallpaper |
| `wallpaper-changer set <image>` | Set a specific image as wallpaper |
| `wallpaper-changer list` | List available wallpapers from configured sources |
| `wallpaper-changer monitors` | Show detected monitors and their geometry |
| `wallpaper-changer config` | Display current configuration |
| `wallpaper-changer config --init` | Create default config file |
| `wallpaper-changer config --edit` | Open config in `$EDITOR` |
| `wallpaper-changer install` | Install systemd user service |
| `wallpaper-changer uninstall` | Remove systemd user service |

### Global Options

| Option | Description |
|--------|-------------|
| `--config <path>` | Use a custom config file |
| `--interval <seconds>` | Override rotation interval |
| `--option <mode>` | Wallpaper scaling: `scaled`, `stretched`, `zoom`, `centered`, `wallpaper`, `none` |

### Examples

```bash
# Quick start: create config, then start
wallpaper-changer config --init
wallpaper-changer config --edit    # add your source folders
wallpaper-changer next             # test with a manual switch

# Run as a systemd service
wallpaper-changer install
systemctl --user start wallpaper-changer

# Set a specific wallpaper
wallpaper-changer set ~/Pictures/wallpaper.jpg

# Override interval to 10 minutes
wallpaper-changer --interval 600 start
```

## Configuration

Config file location: `~/.config/wallpaper-changer/config.toml`

Create a default config with:

```bash
wallpaper-changer config --init
```

### Example `config.toml`

```toml
[general]
interval = 300          # seconds between rotation
option = "scaled"       # scaled | stretched | zoom | centered | wallpaper | none

[[monitors]]
name = "DP-1"
source_folder = "/home/user/Pictures/monitors/DP-1"

[[monitors]]
name = "HDMI-1"
source_folder = "/home/user/Pictures/monitors/HDMI-1"
```

Each `[[monitors]]` entry maps a monitor connector name to a wallpaper source folder. Use `wallpaper-changer monitors` to find your monitor names.

## How It Works

### Monitor Detection

The tool tries detection methods in order:

1. **GNOME Mutter D-Bus** (Wayland) — queries `org.gnome.Mutter.DisplayConfig`
2. **wlr-randr** (wlroots compositors)
3. **xrandr** (X11)

Each monitor's name, resolution, and position are detected.

### Multi-Monitor Composition

GNOME does not natively support per-monitor wallpapers. Wallpaper Changer works around this:

1. Picks a random image from each monitor's source folder
2. Resizes each image to match its monitor's resolution
3. Composites them onto a single canvas using Pillow, positioned according to each monitor's layout
4. Sets the composed image as the desktop background via `gsettings`

### GNOME Integration

Wallpaper is applied using:

```
gsettings set org.gnome.desktop.background picture-uri file:///path/to/image
gsettings set org.gnome.desktop.background picture-uri-dark file:///path/to/image
gsettings set org.gnome.desktop.background picture-options scaled
```

## Development

### Project Structure

```
wallpaper_changer/
├── src/wallpaper_changer/
│   ├── __init__.py
│   ├── cli.py          # CLI interface (argparse)
│   ├── config.py       # TOML configuration management
│   ├── monitor.py      # Monitor detection (D-Bus/xrandr)
│   ├── wallpaper.py    # Wallpaper setting & image composition
│   ├── source.py       # Wallpaper source folder management
│   ├── scheduler.py    # Rotation timer
│   └── systemd.py      # Systemd service management
├── tests/              # Test suite
├── config/             # Example configurations
├── MEMORY.md           # Project memory / decisions
└── TASK.md             # Task tracking
```

### Running Tests

```bash
pip install -e ".[test]"
pytest
```

### Contributing

1. Fork the repository
2. Create a feature branch
3. Add tests for new functionality
4. Ensure all tests pass: `pytest`
5. Submit a pull request

## License

MIT License

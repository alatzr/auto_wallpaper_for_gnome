# Wallpaper Changer

Automatic wallpaper rotation for **Fedora (GNOME Wayland)** with multi-monitor support. Each monitor can display a different wallpaper sourced from its own folder, composited into a single image and applied via GNOME's native `gsettings`.

## Features

- **Multi-monitor support** — assign independent source folders per monitor; images are composited into a single wallpaper
- **Automatic rotation** — configurable interval (default: 300s / 5 min)
- **Random selection** — avoids recently shown wallpapers
- **GUI** — GTK4 + libadwaita with system tray integration
- **CLI interface** — 9 subcommands for full control
- **Systemd integration** — install as a user service for automatic startup
- **Native GNOME** — uses `gsettings`, works on Wayland and X11
- **i18n** — English and Chinese interface

## Installation

### Flatpak (Recommended)

```bash
# Build
flatpak-builder --user --install --force-clean build flatpak/io.github.alatzr.WallpaperChanger.yml

# Run
flatpak run io.github.alatzr.WallpaperChanger
```

### From source

```bash
git clone https://github.com/alatzr/auto_wallpaper_for_gnome.git
cd auto_wallpaper_for_gnome

# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install
pip install -e .

# Run GUI
wallpaper-changer-gui

# Or CLI
wallpaper-changer --help
```

### Install systemd service

```bash
wallpaper-changer install
systemctl --user enable wallpaper-changer
systemctl --user start wallpaper-changer
```

## Usage

### GUI

```bash
wallpaper-changer-gui
```

- **Preview tab** — view current wallpaper, switch to next/random
- **Sources tab** — configure source folder for each monitor
- **Timer tab** — set rotation interval, start/stop
- **Settings tab** — wallpaper scaling, language, minimize to tray

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
```

## Configuration

Config file location: `~/.config/wallpaper-changer/config.toml`

```bash
wallpaper-changer config --init
```

### Example `config.toml`

```toml
[general]
interval = 300          # seconds between rotation
option = "scaled"       # scaled | stretched | zoom | centered | wallpaper | none | spanned

[[monitors]]
name = "DP-1"
source_folder = "/home/user/Pictures/monitors/DP-1"

[[monitors]]
name = "HDMI-1"
source_folder = "/home/user/Pictures/monitors/HDMI-1"
```

Use `wallpaper-changer monitors` to find your monitor names.

## How It Works

### Monitor Detection

1. **GNOME Mutter D-Bus** (Wayland) — queries `org.gnome.Mutter.DisplayConfig`
2. **wlr-randr** (wlroots compositors)
3. **xrandr** (X11)

Detects name, resolution, position, rotation, and scaling factor.

### Multi-Monitor Composition

GNOME does not natively support per-monitor wallpapers. Wallpaper Changer:

1. Picks a random image from each monitor's source folder
2. Composites them onto a single canvas using Pillow, positioned according to each monitor's logical layout
3. Sets the composed image via `gsettings` with `picture-options spanned`

GNOME's `spanned` mode maps the image proportionally across all monitors.

### GNOME Integration

```bash
gsettings set org.gnome.desktop.background picture-uri file:///path/to/image
gsettings set org.gnome.desktop.background picture-uri-dark file:///path/to/image
gsettings set org.gnome.desktop.background picture-options spanned
```

## License

GPL-3.0-or-later

"""Command-line interface for wallpaper-changer."""

import argparse
import sys
from pathlib import Path

from wallpaper_changer.config import Config, CONFIG_FILE
from wallpaper_changer.monitor import get_monitors
from wallpaper_changer.source import WallpaperSource
from wallpaper_changer.wallpaper import set_wallpaper, get_wallpaper
from wallpaper_changer.scheduler import WallpaperScheduler
from wallpaper_changer.systemd import install_service, uninstall_service, is_service_installed


def main():
    parser = create_parser()
    args = parser.parse_args()

    if not hasattr(args, "handler"):
        parser.print_help()
        sys.exit(1)

    try:
        args.handler(args)
    except KeyboardInterrupt:
        print("\nInterrupted.")
        sys.exit(130)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


def create_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="wallpaper-changer",
        description="Automatic wallpaper changer for GNOME with multi-monitor support.",
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=None,
        help="Path to custom config file",
    )
    parser.add_argument(
        "--interval",
        type=int,
        default=None,
        help="Rotation interval in seconds",
    )
    parser.add_argument(
        "--option",
        type=str,
        default=None,
        choices=["scaled", "stretched", "zoom", "centered", "wallpaper", "none"],
        help="Wallpaper scaling option",
    )

    sub = parser.add_subparsers(dest="command")

    p_start = sub.add_parser("start", help="Start automatic wallpaper rotation")
    p_start.set_defaults(handler=cmd_start)

    p_stop = sub.add_parser("stop", help="Stop automatic wallpaper rotation")
    p_stop.set_defaults(handler=cmd_stop)

    p_next = sub.add_parser("next", help="Immediately change to next wallpaper")
    p_next.set_defaults(handler=cmd_next)

    p_set = sub.add_parser("set", help="Set a specific wallpaper image")
    p_set.add_argument("image", type=Path, help="Path to image file")
    p_set.set_defaults(handler=cmd_set)

    p_list = sub.add_parser("list", help="List available wallpapers")
    p_list.set_defaults(handler=cmd_list)

    p_monitors = sub.add_parser("monitors", help="Show detected monitors")
    p_monitors.set_defaults(handler=cmd_monitors)

    p_config = sub.add_parser("config", help="Show or edit configuration")
    p_config.add_argument(
        "--edit",
        action="store_true",
        help="Open config file in editor",
    )
    p_config.add_argument(
        "--init",
        action="store_true",
        help="Create default config file",
    )
    p_config.set_defaults(handler=cmd_config)

    p_install = sub.add_parser("install", help="Install systemd user service")
    p_install.set_defaults(handler=cmd_install)

    p_uninstall = sub.add_parser("uninstall", help="Uninstall systemd user service")
    p_uninstall.set_defaults(handler=cmd_uninstall)

    return parser


def _load_config(args) -> Config:
    config_path = Path(args.config) if args.config else None
    config = Config.load(config_path)
    if args.interval is not None:
        config.interval = args.interval
    if args.option is not None:
        config.option = args.option
    return config


def _pick_image(config: Config) -> Path | None:
    for mc in config.monitors:
        src = WallpaperSource(mc.source_folder)
        img = src.get_random_image()
        if img:
            return img
    return None


def cmd_start(args):
    config = _load_config(args)

    def rotate():
        img = _pick_image(config)
        if img:
            set_wallpaper(str(img), config.option)
            print(f"Wallpaper changed to: {img}")

    scheduler = WallpaperScheduler(callback=rotate, interval=config.interval)
    print(f"Starting wallpaper rotation every {config.interval}s (Ctrl+C to stop)")
    scheduler.run_forever()


def cmd_stop(args):
    print("Wallpaper rotation is managed via systemd. Use 'wallpaper-changer uninstall' to remove the service.")


def cmd_next(args):
    config = _load_config(args)
    img = _pick_image(config)
    if img:
        set_wallpaper(str(img), config.option)
        print(f"Wallpaper changed to: {img}")
    else:
        print("No wallpapers found. Check your config source folders.", file=sys.stderr)
        sys.exit(1)


def cmd_set(args):
    image = args.image.resolve()
    if not image.is_file():
        print(f"File not found: {image}", file=sys.stderr)
        sys.exit(1)
    config = _load_config(args)
    if set_wallpaper(str(image), config.option):
        print(f"Wallpaper set to: {image}")
    else:
        print("Failed to set wallpaper.", file=sys.stderr)
        sys.exit(1)


def cmd_list(args):
    config = _load_config(args)
    if not config.monitors:
        print("No source folders configured. Edit your config to add monitor sources.")
        return

    for mc in config.monitors:
        src = WallpaperSource(mc.source_folder)
        images = src.get_images()
        print(f"[{mc.name}] {mc.source_folder} — {len(images)} image(s)")
        for img in images:
            print(f"  {img}")


def cmd_monitors(args):
    try:
        monitors = get_monitors()
    except RuntimeError as e:
        print(e, file=sys.stderr)
        sys.exit(1)

    for m in monitors:
        primary = " (primary)" if m.is_primary else ""
        scale_info = f" scale={m.scaling}" if m.scaling != 1.0 else ""
        print(f"{m.name}{primary}: {m.geometry}{scale_info}")


def cmd_config(args):
    config_path = Path(args.config) if args.config else CONFIG_FILE

    if args.init:
        config = Config.default()
        config.save(config_path)
        print(f"Config created at {config_path}")
        return

    if args.edit:
        import os
        editor = os.environ.get("EDITOR", "nano")
        config_path.parent.mkdir(parents=True, exist_ok=True)
        if not config_path.exists():
            Config.default().save(config_path)
        import subprocess
        subprocess.run([editor, str(config_path)])
        return

    if config_path.exists():
        print(f"Config file: {config_path}")
        print(config_path.read_text())
    else:
        print(f"No config file found at {config_path}")
        print("Run 'wallpaper-changer config --init' to create one.")


def cmd_install(args):
    config = _load_config(args)
    if install_service(config.interval):
        print("Systemd service installed. Enable with:")
        print(f"  systemctl --user enable wallpaper-changer")
        print(f"  systemctl --user start wallpaper-changer")
    else:
        print("Failed to install service.", file=sys.stderr)
        sys.exit(1)


def cmd_uninstall(args):
    if uninstall_service():
        print("Systemd service uninstalled.")
    else:
        print("Failed to uninstall service.", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()

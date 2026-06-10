import shutil
from pathlib import Path

SERVICE_DIR = Path.home() / ".config" / "systemd" / "user"
SERVICE_NAME = "wallpaper-changer"


def generate_service_file(interval: int = 300) -> str:
    """Generate systemd service file content.

    Args:
        interval: Seconds between wallpaper changes

    Returns:
        Service file content as string
    """
    return f"""[Unit]
Description=Wallpaper Changer - Automatic wallpaper rotation
After=graphical-session.target

[Service]
Type=simple
ExecStart={get_exec_path()}
Restart=on-failure
RestartSec=5
Environment=DISPLAY=:0

[Install]
WantedBy=default.target
"""


def get_exec_path() -> str:
    """Get the executable path for the service.

    Returns:
        Path to the wallpaper-changer executable, or 'wallpaper-changer' as fallback
    """
    path = shutil.which("wallpaper-changer")
    if path:
        return path
    venv_path = Path.home() / ".local" / "bin" / "wallpaper-changer"
    if venv_path.exists():
        return str(venv_path)
    return "wallpaper-changer"


def install_service(interval: int = 300) -> bool:
    """Install and enable the systemd user service.

    Args:
        interval: Seconds between wallpaper changes

    Returns:
        True if successful, False otherwise
    """
    try:
        SERVICE_DIR.mkdir(parents=True, exist_ok=True)
        service_path = SERVICE_DIR / f"{SERVICE_NAME}.service"
        service_path.write_text(generate_service_file(interval))
        return True
    except OSError:
        return False


def uninstall_service() -> bool:
    """Disable and remove the systemd user service.

    Returns:
        True if successful, False otherwise
    """
    try:
        service_path = SERVICE_DIR / f"{SERVICE_NAME}.service"
        if service_path.exists():
            service_path.unlink()
        return True
    except OSError:
        return False


def is_service_installed() -> bool:
    """Check if the service is installed.

    Returns:
        True if the service file exists
    """
    return (SERVICE_DIR / f"{SERVICE_NAME}.service").exists()

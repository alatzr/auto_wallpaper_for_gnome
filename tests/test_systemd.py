import os
import tempfile
from pathlib import Path
from unittest.mock import patch

from wallpaper_changer.systemd import (
    generate_service_file,
    get_exec_path,
    install_service,
    uninstall_service,
    is_service_installed,
    SERVICE_DIR,
    SERVICE_NAME,
)


class TestGenerateServiceFile:
    def test_contains_unit_section(self):
        content = generate_service_file()
        assert "[Unit]" in content
        assert "[Service]" in content
        assert "[Install]" in content

    def test_contains_exec_path(self):
        content = generate_service_file()
        assert "ExecStart=" in content

    def test_contains_display_env(self):
        content = generate_service_file()
        assert "DISPLAY=:0" in content

    def test_wanted_by_default_target(self):
        content = generate_service_file()
        assert "WantedBy=default.target" in content


class TestGetExecPath:
    def test_returns_string(self):
        result = get_exec_path()
        assert isinstance(result, str)

    @patch("wallpaper_changer.systemd.shutil.which", return_value="/usr/bin/wallpaper-changer")
    def test_returns_which_result(self, mock_which):
        result = get_exec_path()
        assert result == "/usr/bin/wallpaper-changer"

    @patch("wallpaper_changer.systemd.shutil.which", return_value=None)
    def test_fallback_when_not_found(self, mock_which):
        result = get_exec_path()
        assert result == "wallpaper-changer"


class TestInstallService:
    def test_install_creates_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            fake_dir = Path(tmpdir) / ".config" / "systemd" / "user"
            with patch("wallpaper_changer.systemd.SERVICE_DIR", fake_dir):
                result = install_service(120)
                assert result is True
                service_file = fake_dir / f"{SERVICE_NAME}.service"
                assert service_file.exists()
                content = service_file.read_text()
                assert "[Unit]" in content

    def test_install_returns_true_if_dir_exists(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            fake_dir = Path(tmpdir) / "existing"
            fake_dir.mkdir()
            with patch("wallpaper_changer.systemd.SERVICE_DIR", fake_dir):
                result = install_service()
                assert result is True


class TestUninstallService:
    def test_uninstall_removes_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            fake_dir = Path(tmpdir)
            service_file = fake_dir / f"{SERVICE_NAME}.service"
            service_file.write_text("dummy")
            with patch("wallpaper_changer.systemd.SERVICE_DIR", fake_dir):
                result = uninstall_service()
                assert result is True
                assert not service_file.exists()

    def test_uninstall_no_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            fake_dir = Path(tmpdir)
            with patch("wallpaper_changer.systemd.SERVICE_DIR", fake_dir):
                result = uninstall_service()
                assert result is True


class TestIsServiceInstalled:
    def test_installed(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            fake_dir = Path(tmpdir)
            (fake_dir / f"{SERVICE_NAME}.service").write_text("dummy")
            with patch("wallpaper_changer.systemd.SERVICE_DIR", fake_dir):
                assert is_service_installed() is True

    def test_not_installed(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            fake_dir = Path(tmpdir)
            with patch("wallpaper_changer.systemd.SERVICE_DIR", fake_dir):
                assert is_service_installed() is False

import pytest
from pathlib import Path
from wallpaper_changer.config import Config, MonitorConfig, CONFIG_DIR, CONFIG_FILE


def test_default_config():
    config = Config.default()
    assert config.interval == 300
    assert config.option == "scaled"
    assert config.monitors == []


def test_monitor_config():
    monitor = MonitorConfig(name="DP-1", source_folder="/path/to/wallpapers")
    assert monitor.name == "DP-1"
    assert monitor.source_folder == "/path/to/wallpapers"


def test_config_with_monitors():
    monitors = [
        MonitorConfig(name="DP-1", source_folder="/path1"),
        MonitorConfig(name="DP-2", source_folder="/path2"),
    ]
    config = Config(interval=600, option="stretched", monitors=monitors)
    assert config.interval == 600
    assert config.option == "stretched"
    assert len(config.monitors) == 2
    assert config.monitors[0].name == "DP-1"


def test_save_and_load(tmp_path):
    config_path = tmp_path / "config.toml"
    monitors = [
        MonitorConfig(name="DP-1", source_folder="/wallpapers/monitor1"),
        MonitorConfig(name="HDMI-1", source_folder="/wallpapers/monitor2"),
    ]
    config = Config(interval=120, option="centered", monitors=monitors)
    config.save(config_path)

    loaded = Config.load(config_path)
    assert loaded.interval == 120
    assert loaded.option == "centered"
    assert len(loaded.monitors) == 2
    assert loaded.monitors[0].name == "DP-1"
    assert loaded.monitors[0].source_folder == "/wallpapers/monitor1"
    assert loaded.monitors[1].name == "HDMI-1"


def test_load_nonexistent_returns_default(tmp_path):
    config_path = tmp_path / "nonexistent.toml"
    config = Config.load(config_path)
    assert config.interval == 300
    assert config.option == "scaled"
    assert config.monitors == []


def test_save_creates_directory(tmp_path):
    config_path = tmp_path / "subdir" / "config.toml"
    config = Config(interval=60, option="scaled")
    config.save(config_path)
    assert config_path.exists()


def test_ensure_config_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "wallpaper_changer.config.CONFIG_DIR", tmp_path / "test_dir"
    )
    config = Config()
    config.ensure_config_dir()
    assert (tmp_path / "test_dir").exists()


def test_config_constants():
    assert CONFIG_DIR == Path.home() / ".config" / "wallpaper-changer"
    assert CONFIG_FILE == CONFIG_DIR / "config.toml"


def test_save_empty_monitors(tmp_path):
    config_path = tmp_path / "config.toml"
    config = Config(interval=300, option="scaled", monitors=[])
    config.save(config_path)

    loaded = Config.load(config_path)
    assert loaded.interval == 300
    assert loaded.monitors == []


def test_roundtrip_all_options(tmp_path):
    config_path = tmp_path / "config.toml"
    monitors = [
        MonitorConfig(name="DP-1", source_folder="/a"),
        MonitorConfig(name="DP-2", source_folder="/b"),
        MonitorConfig(name="HDMI-1", source_folder="/c"),
    ]
    original = Config(interval=999, option="wallpaper", monitors=monitors)
    original.save(config_path)

    loaded = Config.load(config_path)
    assert loaded.interval == original.interval
    assert loaded.option == original.option
    assert len(loaded.monitors) == len(original.monitors)
    for orig, load in zip(original.monitors, loaded.monitors):
        assert orig.name == load.name
        assert orig.source_folder == load.source_folder

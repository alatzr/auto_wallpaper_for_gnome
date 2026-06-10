from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional
import tomllib
import tomli_w

CONFIG_DIR = Path.home() / ".config" / "wallpaper-changer"
CONFIG_FILE = CONFIG_DIR / "config.toml"


@dataclass
class MonitorConfig:
    name: str
    source_folder: str


@dataclass
class Config:
    interval: int = 300
    option: str = "scaled"
    minimize_to_tray: bool = False
    language: str = ""
    monitors: list[MonitorConfig] = field(default_factory=list)

    @classmethod
    def load(cls, config_path: Optional[Path] = None) -> "Config":
        """Load config from file."""
        path = config_path or CONFIG_FILE
        if not path.exists():
            return cls.default()

        with open(path, "rb") as f:
            data = tomllib.load(f)

        general = data.get("general", {})
        monitors_data = data.get("monitors", [])
        monitors = [MonitorConfig(**m) for m in monitors_data]

        return cls(
            interval=general.get("interval", 300),
            option=general.get("option", "scaled"),
            minimize_to_tray=general.get("minimize_to_tray", False),
            language=general.get("language", ""),
            monitors=monitors,
        )

    def save(self, config_path: Optional[Path] = None):
        """Save config to file."""
        path = config_path or CONFIG_FILE
        path.parent.mkdir(parents=True, exist_ok=True)

        data = {
            "general": {
                "interval": self.interval,
                "option": self.option,
                "minimize_to_tray": self.minimize_to_tray,
                "language": self.language,
            },
            "monitors": [
                {"name": m.name, "source_folder": m.source_folder}
                for m in self.monitors
            ],
        }

        with open(path, "wb") as f:
            tomli_w.dump(data, f)

    @classmethod
    def default(cls) -> "Config":
        """Create default config."""
        return cls(
            interval=300,
            option="scaled",
            monitors=[],
        )

    def ensure_config_dir(self):
        """Create config directory if it doesn't exist."""
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)

"""Wallpaper source folder management with random selection and history tracking."""

from __future__ import annotations

import json
import random
from pathlib import Path
from typing import Optional

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".webp", ".gif"}


class WallpaperSource:
    """Manages wallpaper source folders and random selection."""

    def __init__(self, folder_path: str, history_file: Optional[str] = None):
        self.folder = Path(folder_path)
        self.history_file = Path(history_file) if history_file else None
        self.history: list[str] = []
        self._load_history()

    def get_images(self) -> list[Path]:
        """Get list of all image files in the folder (recursive)."""
        if not self.folder.is_dir():
            return []
        return sorted(
            p
            for p in self.folder.rglob("*")
            if p.is_file() and p.suffix.lower() in IMAGE_EXTENSIONS
        )

    def get_random_image(self, avoid_recent: int = 5) -> Optional[Path]:
        """Get a random image from the folder, avoiding recently used ones.

        Args:
            avoid_recent: Number of recent history entries to exclude from selection.

        Returns:
            Path to a random image, or None if no images are available.
        """
        images = self.get_images()
        if not images:
            return None

        recent_set = set(self.history[-avoid_recent:]) if avoid_recent > 0 else set()
        candidates = [img for img in images if str(img) not in recent_set]

        if not candidates:
            candidates = images

        chosen = random.choice(candidates)
        self.history.append(str(chosen))
        self._save_history()
        return chosen

    def _load_history(self) -> None:
        """Load history from file."""
        if self.history_file and self.history_file.is_file():
            try:
                data = json.loads(self.history_file.read_text())
                if isinstance(data, list):
                    self.history = [str(p) for p in data]
            except (json.JSONDecodeError, OSError):
                self.history = []

    def _save_history(self) -> None:
        """Save history to file."""
        if self.history_file:
            self.history_file.parent.mkdir(parents=True, exist_ok=True)
            self.history_file.write_text(json.dumps(self.history, indent=2))

    def clear_history(self) -> None:
        """Clear history."""
        self.history.clear()
        self._save_history()

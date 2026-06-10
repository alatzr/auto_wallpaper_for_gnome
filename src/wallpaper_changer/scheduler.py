import signal
import time
import threading
from typing import Callable, Optional


class WallpaperScheduler:
    """Scheduler for automatic wallpaper rotation."""

    def __init__(self, callback: Callable[[], None], interval: int = 300):
        """
        Args:
            callback: Function to call for wallpaper change
            interval: Seconds between changes
        """
        self.callback = callback
        self._interval = interval
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()

    @property
    def interval(self) -> int:
        return self._interval

    @interval.setter
    def interval(self, value: int) -> None:
        self._interval = value

    def start(self):
        """Start the scheduler in background thread."""
        if self._running:
            return
        self._stop_event.clear()
        self._running = True
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()

    def stop(self):
        """Stop the scheduler."""
        if not self._running:
            return
        self._running = False
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=2)
            self._thread = None

    def run_forever(self):
        """Run in foreground (blocking). Handles SIGINT/SIGTERM for graceful shutdown."""
        original_sigint = signal.getsignal(signal.SIGINT)
        original_sigterm = signal.getsignal(signal.SIGTERM)

        def _shutdown_handler(signum, frame):
            self.stop()

        signal.signal(signal.SIGINT, _shutdown_handler)
        signal.signal(signal.SIGTERM, _shutdown_handler)

        try:
            self.start()
            while self._running:
                time.sleep(0.5)
        finally:
            signal.signal(signal.SIGINT, original_sigint)
            signal.signal(signal.SIGTERM, original_sigterm)

    def _run_loop(self):
        """Internal loop that calls callback at interval."""
        while self._running:
            try:
                self.callback()
            except Exception:
                pass
            # Sleep in small increments so we can respond to stop/interval changes
            elapsed = 0
            while self._running and elapsed < self._interval:
                time.sleep(0.5)
                elapsed += 0.5

    def is_running(self) -> bool:
        """Check if scheduler is running."""
        return self._running

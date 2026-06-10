import time
import threading
from unittest.mock import MagicMock

from wallpaper_changer.scheduler import WallpaperScheduler


class TestWallpaperScheduler:
    def test_init_defaults(self):
        cb = MagicMock()
        s = WallpaperScheduler(cb)
        assert s.interval == 300
        assert s.callback is cb
        assert s.is_running() is False

    def test_init_custom_interval(self):
        s = WallpaperScheduler(MagicMock(), interval=60)
        assert s.interval == 60

    def test_start_stop(self):
        cb = MagicMock()
        s = WallpaperScheduler(cb, interval=1)
        s.start()
        assert s.is_running() is True
        assert s._thread is not None
        s.stop()
        assert s.is_running() is False

    def test_start_idempotent(self):
        s = WallpaperScheduler(MagicMock(), interval=1)
        s.start()
        thread1 = s._thread
        s.start()
        assert s._thread is thread1
        s.stop()

    def test_stop_idempotent(self):
        s = WallpaperScheduler(MagicMock(), interval=1)
        s.stop()
        assert s.is_running() is False

    def test_callback_called(self):
        cb = MagicMock()
        s = WallpaperScheduler(cb, interval=1)
        s.start()
        time.sleep(1.5)
        s.stop()
        assert cb.call_count >= 1

    def test_callback_exception_does_not_stop(self):
        call_count = 0

        def bad_callback():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise RuntimeError("boom")

        s = WallpaperScheduler(bad_callback, interval=1)
        s.start()
        time.sleep(2.5)
        s.stop()
        assert call_count >= 2

    def test_run_forever_stops_on_signal(self):
        cb = MagicMock()
        s = WallpaperScheduler(cb, interval=1)

        def stop_after_delay():
            time.sleep(1.5)
            s.stop()

        threading.Thread(target=stop_after_delay, daemon=True).start()
        s.run_forever()
        assert s.is_running() is False

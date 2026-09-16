"""Session-local background capture; snapshots never wait for camera or worker."""
import threading


class CountdownCapture:
    def __init__(self, capture):
        self._lock = threading.Lock()
        self._jpeg = None
        self.finished = threading.Event()
        self.stop = threading.Event()
        self.error = None
        self._thread = threading.Thread(target=self._run, args=(capture,), daemon=True)

    def start(self):
        self._thread.start()

    def _publish(self, jpeg):
        with self._lock:
            self._jpeg = jpeg

    def _run(self, capture):
        try:
            jpeg = capture(on_candidate=self._publish, stop_event=self.stop)
            if jpeg:
                self._publish(jpeg)
        except Exception as exc:
            self.error = str(exc)
        finally:
            self.finished.set()

    def snapshot(self):
        with self._lock:
            return self._jpeg

from artifact.hardware.runner import HardwareRunner


class _FakeNotifySocket:
    def __init__(self) -> None:
        self.address = None
        self.payload = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback) -> None:
        return None

    def connect(self, address) -> None:
        self.address = address

    def sendall(self, payload: bytes) -> None:
        self.payload = payload


def test_systemd_ready_notification_supports_cyrillic(monkeypatch) -> None:
    fake = _FakeNotifySocket()
    monkeypatch.setenv("NOTIFY_SOCKET", "/run/systemd/notify")
    monkeypatch.setattr(
        "artifact.hardware.runner.socket.socket",
        lambda *args, **kwargs: fake,
    )

    message = "READY=1\nSTATUS=ФОТОБУДКА ВИНОВНИЦЫ hardware loop running"

    assert HardwareRunner._systemd_notify(message) is True
    assert fake.address == "/run/systemd/notify"
    assert fake.payload == message.encode("utf-8")


def test_systemd_notification_supports_abstract_socket(monkeypatch) -> None:
    fake = _FakeNotifySocket()
    monkeypatch.setenv("NOTIFY_SOCKET", "@artifact-notify")
    monkeypatch.setattr(
        "artifact.hardware.runner.socket.socket",
        lambda *args, **kwargs: fake,
    )

    assert HardwareRunner._systemd_notify("WATCHDOG=1") is True
    assert fake.address == "\0artifact-notify"
    assert fake.payload == b"WATCHDOG=1"


def test_systemd_notification_is_optional(monkeypatch) -> None:
    monkeypatch.delenv("NOTIFY_SOCKET", raising=False)

    assert HardwareRunner._systemd_notify("READY=1") is False

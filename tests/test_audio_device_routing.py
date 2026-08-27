import os
from types import SimpleNamespace

from artifact.core.events import EventBus
from artifact.hardware import runner as runner_module


class _FakeMixer:
    def __init__(self) -> None:
        self.initialized = False

    def quit(self) -> None:
        pass

    def pre_init(self, **_kwargs) -> None:
        pass

    def init(self) -> None:
        self.initialized = True

    def set_num_channels(self, _count: int) -> None:
        pass


def test_hardware_audio_uses_stable_default_route(monkeypatch) -> None:
    mixer = _FakeMixer()
    fake_pygame = SimpleNamespace(mixer=mixer)
    fake_engine = SimpleNamespace(_initialized=False, _load_generated_sounds=lambda: None)

    monkeypatch.delenv("AUDIODEV", raising=False)
    monkeypatch.delenv("SDL_AUDIODRIVER", raising=False)
    monkeypatch.setattr(runner_module, "_get_pygame", lambda: fake_pygame)
    monkeypatch.setattr(runner_module, "get_audio_engine", lambda: fake_engine)
    monkeypatch.setattr("subprocess.run", lambda *_args, **_kwargs: None)

    runner = runner_module.HardwareRunner(event_bus=EventBus())
    assert runner._init_audio() is True
    assert mixer.initialized is True
    assert os.environ["AUDIODEV"] == "default"
    assert os.environ["SDL_AUDIODRIVER"] == "alsa"
    assert fake_engine._initialized is True


def test_hardware_audio_respects_explicit_service_route(monkeypatch) -> None:
    mixer = _FakeMixer()
    fake_engine = SimpleNamespace(_initialized=False, _load_generated_sounds=lambda: None)

    monkeypatch.setenv("AUDIODEV", "custom-stable-route")
    monkeypatch.setattr(
        runner_module,
        "_get_pygame",
        lambda: SimpleNamespace(mixer=mixer),
    )
    monkeypatch.setattr(runner_module, "get_audio_engine", lambda: fake_engine)
    monkeypatch.setattr("subprocess.run", lambda *_args, **_kwargs: None)

    runner = runner_module.HardwareRunner(event_bus=EventBus())
    assert runner._init_audio() is True
    assert os.environ["AUDIODEV"] == "custom-stable-route"

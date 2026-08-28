from artifact.core.events import EventBus
from artifact.hardware import runner as runner_module


def test_legacy_gpio_buttons_can_be_disabled_fail_closed(monkeypatch) -> None:
    monkeypatch.setenv("ARTIFACT_DISABLE_GPIO_BUTTONS", "true")

    runner = runner_module.HardwareRunner(event_bus=EventBus())
    assert runner._init_gpio_buttons() is False
    assert runner._gpio_initialized is False
    assert runner._gpio_left_button is None
    assert runner._gpio_right_button is None

    # Polling remains a no-op even when called every hardware frame.
    runner._poll_gpio_buttons()
    assert runner.event_bus.get_history(limit=10) == []

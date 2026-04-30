from __future__ import annotations

from dataclasses import dataclass


@dataclass
class EdgeDeviceState:
    muted: bool = False
    led_state: str = "idle"
    interaction_active: bool = False
    last_event: str = "init"


class EdgeDeviceController:
    def __init__(self) -> None:
        self.state = EdgeDeviceState()

    def set_mute(self, enabled: bool) -> None:
        self.state.muted = enabled
        self.state.last_event = "mute_on" if enabled else "mute_off"
        if enabled:
            self.state.led_state = "muted"
        elif not self.state.interaction_active:
            self.state.led_state = "idle"

    def toggle_mute(self) -> bool:
        self.set_mute(not self.state.muted)
        return self.state.muted

    def start_interaction(self) -> None:
        self.state.interaction_active = True
        self.state.led_state = "listening"
        self.state.last_event = "interaction_started"

    def mark_sending(self) -> None:
        self.state.led_state = "sending"
        self.state.last_event = "audio_sending"

    def mark_speaking(self) -> None:
        self.state.led_state = "muted" if self.state.muted else "speaking"
        self.state.last_event = "response_speaking"

    def mark_error(self) -> None:
        self.state.led_state = "error"
        self.state.last_event = "interaction_error"
        self.state.interaction_active = False

    def finish_interaction(self) -> None:
        self.state.interaction_active = False
        self.state.led_state = "muted" if self.state.muted else "idle"
        self.state.last_event = "interaction_finished"

    def press_button(self) -> None:
        self.state.interaction_active = False
        self.state.led_state = "muted" if self.state.muted else "idle"
        self.state.last_event = "button_pressed"

    def describe(self) -> str:
        return (
            f"led={self.state.led_state}, muted={self.state.muted}, "
            f"interaction_active={self.state.interaction_active}, event={self.state.last_event}"
        )

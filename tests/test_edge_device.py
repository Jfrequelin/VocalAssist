from __future__ import annotations

import unittest

from src.assistant.edge_device import EdgeDeviceController


class TestEdgeDeviceController(unittest.TestCase):
    def test_mute_updates_led_state(self) -> None:
        controller = EdgeDeviceController()
        controller.set_mute(True)
        self.assertTrue(controller.state.muted)
        self.assertEqual(controller.state.led_state, "muted")

    def test_interaction_flow_updates_states(self) -> None:
        controller = EdgeDeviceController()
        controller.start_interaction()
        self.assertTrue(controller.state.interaction_active)
        self.assertEqual(controller.state.led_state, "listening")

        controller.mark_sending()
        self.assertEqual(controller.state.led_state, "sending")

        controller.mark_speaking()
        self.assertEqual(controller.state.led_state, "speaking")

        controller.finish_interaction()
        self.assertFalse(controller.state.interaction_active)
        self.assertEqual(controller.state.led_state, "idle")

    def test_button_cuts_interaction(self) -> None:
        controller = EdgeDeviceController()
        controller.start_interaction()
        controller.press_button()
        self.assertFalse(controller.state.interaction_active)
        self.assertEqual(controller.state.last_event, "button_pressed")


if __name__ == "__main__":
    unittest.main()

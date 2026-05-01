from __future__ import annotations

import unittest

from src.assistant.session_manager import SessionManager, SessionState


class TestSessionManager(unittest.TestCase):
    def test_new_session_starts_active(self) -> None:
        manager = SessionManager(timeout_seconds=30)
        session = manager.start_session()
        self.assertEqual(session.state, SessionState.ACTIVE)
        self.assertIsNotNone(session.session_id)

    def test_session_expires_after_timeout(self) -> None:
        manager = SessionManager(timeout_seconds=0.05)
        session = manager.start_session()
        session_id = session.session_id

        self.assertTrue(manager.is_session_active(session_id))

        import time as time_module
        time_module.sleep(0.3)

        self.assertFalse(manager.is_session_active(session_id))

    def test_session_resume_within_expiry(self) -> None:
        manager = SessionManager(timeout_seconds=30)
        session = manager.start_session()
        session_id = session.session_id

        self.assertTrue(manager.is_session_active(session_id))

        resumed = manager.resume_session(session_id)
        assert resumed is not None
        self.assertEqual(resumed.state, SessionState.ACTIVE)

    def test_session_cannot_resume_after_expiry(self) -> None:
        manager = SessionManager(timeout_seconds=0.05)
        session = manager.start_session()
        session_id = session.session_id

        import time as time_module
        time_module.sleep(0.3)

        resumed = manager.resume_session(session_id)
        self.assertIsNone(resumed)

    def test_explicit_session_close(self) -> None:
        manager = SessionManager(timeout_seconds=30)
        session = manager.start_session()
        session_id = session.session_id

        manager.close_session(session_id)

        self.assertFalse(manager.is_session_active(session_id))

    def test_multiple_sessions_independent(self) -> None:
        manager = SessionManager(timeout_seconds=30)
        session1 = manager.start_session()
        session2 = manager.start_session()

        self.assertTrue(manager.is_session_active(session1.session_id))
        self.assertTrue(manager.is_session_active(session2.session_id))

        manager.close_session(session1.session_id)

        self.assertFalse(manager.is_session_active(session1.session_id))
        self.assertTrue(manager.is_session_active(session2.session_id))

    def test_session_activity_extends_timeout(self) -> None:
        manager = SessionManager(timeout_seconds=0.1)
        session = manager.start_session()
        session_id = session.session_id

        import time as time_module
        time_module.sleep(0.08)

        manager.record_activity(session_id)

        time_module.sleep(0.08)

        self.assertTrue(manager.is_session_active(session_id))


if __name__ == "__main__":
    unittest.main()

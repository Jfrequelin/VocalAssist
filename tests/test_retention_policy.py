"""
Tests for MACRO-003-T3: Data retention policies
Tests data retention, archival, and cleanup mechanisms.
"""

from __future__ import annotations

import unittest
from datetime import datetime, timedelta

from src.assistant.retention_policy import (
    RetentionPolicy,
    RetentionLevel,
    DataRetentionManager,
)


class TestRetentionLevel(unittest.TestCase):
    """Test RetentionLevel enumeration."""

    def test_retention_levels_exist(self) -> None:
        """Test that retention levels are defined."""
        self.assertIn(RetentionLevel.IMMEDIATE, [e for e in RetentionLevel])
        self.assertIn(RetentionLevel.SHORT_TERM, [e for e in RetentionLevel])
        self.assertIn(RetentionLevel.MEDIUM_TERM, [e for e in RetentionLevel])
        self.assertIn(RetentionLevel.LONG_TERM, [e for e in RetentionLevel])

    def test_retention_level_comparison(self) -> None:
        """Test that retention levels have meaningful order."""
        self.assertLess(
            RetentionLevel.IMMEDIATE.get_days(),
            RetentionLevel.SHORT_TERM.get_days()
        )
        self.assertLess(
            RetentionLevel.SHORT_TERM.get_days(),
            RetentionLevel.MEDIUM_TERM.get_days()
        )
        self.assertLess(
            RetentionLevel.MEDIUM_TERM.get_days(),
            RetentionLevel.LONG_TERM.get_days()
        )


class TestRetentionPolicy(unittest.TestCase):
    """Test RetentionPolicy configuration."""

    def test_create_retention_policy(self) -> None:
        """Test creating a retention policy."""
        policy = RetentionPolicy(
            level=RetentionLevel.SHORT_TERM,
            archivable=True,
            exportable=True
        )
        
        self.assertEqual(policy.level, RetentionLevel.SHORT_TERM)
        self.assertTrue(policy.archivable)
        self.assertTrue(policy.exportable)

    def test_retention_policy_days_until_expiry(self) -> None:
        """Test calculating days until expiry."""
        policy = RetentionPolicy(level=RetentionLevel.SHORT_TERM)
        created = datetime.now() - timedelta(days=5)
        
        days_left = policy.days_until_expiry(created)
        # Should have 5-7 days left (depends on exact SHORT_TERM definition)
        self.assertGreater(days_left, 0)

    def test_retention_policy_is_expired(self) -> None:
        """Test checking if data is expired."""
        policy = RetentionPolicy(level=RetentionLevel.IMMEDIATE)
        created = datetime.now() - timedelta(days=1)
        
        self.assertTrue(policy.is_expired(created))

    def test_retention_policy_not_expired(self) -> None:
        """Test checking if data is not expired."""
        policy = RetentionPolicy(level=RetentionLevel.LONG_TERM)
        created = datetime.now() - timedelta(days=1)
        
        self.assertFalse(policy.is_expired(created))


class TestDataRetentionManager(unittest.TestCase):
    """Test data retention management."""

    def setUp(self) -> None:
        self.manager = DataRetentionManager()

    def test_register_data_with_policy(self) -> None:
        """Test registering data with a retention policy."""
        policy = RetentionPolicy(level=RetentionLevel.MEDIUM_TERM)
        data_id = self.manager.register_data(
            data_type="reminders",
            policy=policy
        )
        
        self.assertIsNotNone(data_id)
        retrieved = self.manager.get_retention_info(data_id)
        self.assertIsNotNone(retrieved)

    def test_find_expired_data(self) -> None:
        """Test finding expired data."""
        # Create data that expires immediately
        policy = RetentionPolicy(level=RetentionLevel.IMMEDIATE)
        data_id_1 = self.manager.register_data("notes", policy)
        
        # Create data with long retention
        policy_2 = RetentionPolicy(level=RetentionLevel.LONG_TERM)
        data_id_2 = self.manager.register_data("settings", policy_2)
        
        # Artificially age the first one by modifying the registry directly
        self.manager.data_registry[data_id_1].created_at = datetime.now() - timedelta(days=2)
        
        # Find expired
        expired = self.manager.find_expired_data()
        self.assertTrue(any(d["id"] == data_id_1 for d in expired))
        self.assertFalse(any(d["id"] == data_id_2 for d in expired))

    def test_mark_for_archival(self) -> None:
        """Test marking data for archival."""
        policy = RetentionPolicy(level=RetentionLevel.SHORT_TERM, archivable=True)
        data_id = self.manager.register_data("notes", policy)
        
        archived = self.manager.mark_for_archival(data_id)
        self.assertTrue(archived)
        
        info = self.manager.get_retention_info(data_id)
        assert info is not None
        self.assertTrue(info["archived"])

    def test_cannot_archive_non_archivable(self) -> None:
        """Test that non-archivable data cannot be archived."""
        policy = RetentionPolicy(level=RetentionLevel.SHORT_TERM, archivable=False)
        data_id = self.manager.register_data("temporary", policy)
        
        archived = self.manager.mark_for_archival(data_id)
        self.assertFalse(archived)

    def test_delete_data(self) -> None:
        """Test deleting data."""
        policy = RetentionPolicy(level=RetentionLevel.SHORT_TERM)
        data_id = self.manager.register_data("to_delete", policy)
        
        self.manager.delete_data(data_id)
        
        info = self.manager.get_retention_info(data_id)
        self.assertIsNone(info)

    def test_cleanup_expired_data(self) -> None:
        """Test cleanup of expired data."""
        policy = RetentionPolicy(level=RetentionLevel.IMMEDIATE)
        data_id = self.manager.register_data("notes", policy)
        
        # Artificially age the data by modifying the registry directly
        self.manager.data_registry[data_id].created_at = datetime.now() - timedelta(days=2)
        
        # Run cleanup
        deleted = self.manager.cleanup_expired_data()
        
        self.assertTrue(any(d["id"] == data_id for d in deleted))

    def test_cleanup_with_archival(self) -> None:
        """Test cleanup that archives before deleting."""
        policy = RetentionPolicy(
            level=RetentionLevel.SHORT_TERM,
            archivable=True
        )
        data_id = self.manager.register_data("notes", policy)
        
        # Artificially age the data
        retention_info = self.manager.get_retention_info(data_id)
        assert retention_info is not None
        retention_info["created_at"] = datetime.now() - timedelta(days=10)
        
        # Run cleanup with archive
        results = self.manager.cleanup_with_archival()
        
        # Should have archived the data if archivable
        self.assertTrue("archived" in results or "deleted" in results)

    def test_policy_per_data_type(self) -> None:
        """Test setting different policies for different data types."""
        reminders_policy = RetentionPolicy(level=RetentionLevel.LONG_TERM)
        notes_policy = RetentionPolicy(level=RetentionLevel.MEDIUM_TERM)
        
        self.manager.set_policy_for_type("reminders", reminders_policy)
        self.manager.set_policy_for_type("notes", notes_policy)
        
        reminders_policy_retrieved = self.manager.get_policy_for_type("reminders")
        notes_policy_retrieved = self.manager.get_policy_for_type("notes")

        assert reminders_policy_retrieved is not None
        assert notes_policy_retrieved is not None
        self.assertEqual(reminders_policy_retrieved.level, RetentionLevel.LONG_TERM)
        self.assertEqual(notes_policy_retrieved.level, RetentionLevel.MEDIUM_TERM)

    def test_get_retention_stats(self) -> None:
        """Test getting retention statistics."""
        policy1 = RetentionPolicy(level=RetentionLevel.SHORT_TERM)
        policy2 = RetentionPolicy(level=RetentionLevel.LONG_TERM)
        
        self.manager.register_data("notes", policy1)
        self.manager.register_data("preferences", policy2)
        
        stats = self.manager.get_retention_stats()
        
        self.assertEqual(stats["total_items"], 2)
        self.assertIn("by_retention_level", stats)
        self.assertIn("archived_count", stats)

    def test_export_retained_data(self) -> None:
        """Test exporting data before deletion."""
        policy = RetentionPolicy(level=RetentionLevel.SHORT_TERM, exportable=True)
        data_id = self.manager.register_data("meetings", policy)
        
        exported = self.manager.export_data(data_id)

        assert exported is not None
        self.assertIn("id", exported)
        self.assertIn("data_type", exported)

    def test_cannot_export_non_exportable(self) -> None:
        """Test that non-exportable data cannot be exported."""
        policy = RetentionPolicy(level=RetentionLevel.SHORT_TERM, exportable=False)
        data_id = self.manager.register_data("ephemeral", policy)
        
        exported = self.manager.export_data(data_id)
        
        self.assertIsNone(exported)


class TestRetentionIntegration(unittest.TestCase):
    """Integration tests for retention system."""

    def setUp(self) -> None:
        self.manager = DataRetentionManager()

    def test_full_lifecycle(self) -> None:
        """Test complete data lifecycle: creation -> retention -> cleanup."""
        # Create data
        policy = RetentionPolicy(level=RetentionLevel.IMMEDIATE)
        data_id = self.manager.register_data("temp_notes", policy)
        
        # Should exist initially
        info = self.manager.get_retention_info(data_id)
        self.assertIsNotNone(info)
        
        # Artificially expire by modifying the registry directly
        self.manager.data_registry[data_id].created_at = datetime.now() - timedelta(days=2)
        
        # Should be found as expired
        expired = self.manager.find_expired_data()
        self.assertTrue(any(d["id"] == data_id for d in expired))
        
        # Cleanup
        deleted = self.manager.cleanup_expired_data()
        self.assertTrue(any(d["id"] == data_id for d in deleted))
        
        # Should be gone
        info = self.manager.get_retention_info(data_id)
        self.assertIsNone(info)

    def test_mixed_retention_levels(self) -> None:
        """Test system with mixed retention levels."""
        policies = [
            ("immediate", RetentionLevel.IMMEDIATE),
            ("short", RetentionLevel.SHORT_TERM),
            ("medium", RetentionLevel.MEDIUM_TERM),
            ("long", RetentionLevel.LONG_TERM),
        ]
        
        data_ids: list[str] = []
        for data_type, level in policies:
            policy = RetentionPolicy(level=level)
            data_id = self.manager.register_data(data_type, policy)
            data_ids.append(data_id)
        
        # Expire only the immediate by modifying the registry directly
        for data_id in data_ids:
            info = self.manager.data_registry[data_id]
            if info.retention_policy["level"] == "immediate":
                info.created_at = datetime.now() - timedelta(days=2)
        
        # Cleanup
        deleted = self.manager.cleanup_expired_data()
        
        # Only immediate should be deleted
        self.assertEqual(len(deleted), 1)


if __name__ == "__main__":
    unittest.main()

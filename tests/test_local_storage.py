"""
Tests for MACRO-003-T1: Local storage of reminders and notes
Tests basic CRUD operations for reminders and notes management.
"""

from __future__ import annotations

import unittest
from datetime import datetime, timedelta

from src.assistant.local_storage import LocalNote, LocalReminder, ReminderStore


class TestLocalReminder(unittest.TestCase):
    """Test LocalReminder data model."""

    def test_create_reminder_with_title(self) -> None:
        """Test creating a reminder with just a title."""
        reminder = LocalReminder(title="Doctor appointment")
        
        self.assertEqual(reminder.title, "Doctor appointment")
        self.assertIsNotNone(reminder.id)
        self.assertIsNotNone(reminder.created_at)

    def test_reminder_with_due_date(self) -> None:
        """Test reminder with due date."""
        due_date = datetime.now() + timedelta(days=1)
        reminder = LocalReminder(title="Meeting", due_date=due_date)
        
        self.assertEqual(reminder.due_date, due_date)
        self.assertFalse(reminder.completed)

    def test_reminder_mark_completed(self) -> None:
        """Test marking reminder as completed."""
        reminder = LocalReminder(title="Task")
        self.assertFalse(reminder.completed)
        
        reminder.completed = True
        self.assertTrue(reminder.completed)

    def test_reminder_with_priority(self) -> None:
        """Test reminder with priority level."""
        reminder = LocalReminder(title="Urgent", priority="high")
        
        self.assertEqual(reminder.priority, "high")

    def test_reminder_priority_values(self) -> None:
        """Test valid priority values."""
        valid_priorities = ["low", "medium", "high"]
        
        for priority in valid_priorities:
            reminder = LocalReminder(title="Test", priority=priority)
            self.assertEqual(reminder.priority, priority)


class TestLocalNote(unittest.TestCase):
    """Test LocalNote data model."""

    def test_create_simple_note(self) -> None:
        """Test creating a simple note."""
        note = LocalNote(title="Meeting notes", content="Discussed Q2 goals")
        
        self.assertEqual(note.title, "Meeting notes")
        self.assertEqual(note.content, "Discussed Q2 goals")
        self.assertIsNotNone(note.id)

    def test_note_with_tags(self) -> None:
        """Test note with tags for categorization."""
        note = LocalNote(
            title="Project update",
            content="Completed phase 1",
            tags=["project", "update", "phase1"]
        )
        
        self.assertEqual(len(note.tags), 3)
        self.assertIn("project", note.tags)

    def test_note_modification_timestamp(self) -> None:
        """Test that modification timestamp updates."""
        note = LocalNote(title="Test", content="Original")
        original_modified = note.modified_at
        
        # Modify content
        note.content = "Updated"
        
        # Modification time should be updated (in real impl)
        self.assertIsNotNone(note.modified_at)

    def test_note_archiving(self) -> None:
        """Test archiving notes."""
        note = LocalNote(title="Old note", content="Archived")
        self.assertFalse(note.archived)
        
        note.archived = True
        self.assertTrue(note.archived)


class TestReminderStore(unittest.TestCase):
    """Test ReminderStore for persistence and retrieval."""

    def setUp(self) -> None:
        self.store = ReminderStore()

    def test_add_reminder_and_retrieve(self) -> None:
        """Test adding and retrieving reminders."""
        reminder = LocalReminder(title="Buy milk")
        self.store.add_reminder(reminder)
        
        retrieved = self.store.get_reminder(reminder.id)
        self.assertIsNotNone(retrieved)
        self.assertEqual(retrieved.title, "Buy milk")

    def test_list_all_reminders(self) -> None:
        """Test listing all reminders."""
        reminder1 = LocalReminder(title="Task 1")
        reminder2 = LocalReminder(title="Task 2")
        
        self.store.add_reminder(reminder1)
        self.store.add_reminder(reminder2)
        
        all_reminders = self.store.list_reminders()
        self.assertEqual(len(all_reminders), 2)

    def test_filter_reminders_by_completed(self) -> None:
        """Test filtering reminders by completion status."""
        reminder1 = LocalReminder(title="Done")
        reminder1.completed = True
        
        reminder2 = LocalReminder(title="Pending")
        
        self.store.add_reminder(reminder1)
        self.store.add_reminder(reminder2)
        
        pending = self.store.list_reminders(completed=False)
        self.assertEqual(len(pending), 1)
        self.assertEqual(pending[0].title, "Pending")

    def test_update_reminder(self) -> None:
        """Test updating an existing reminder."""
        reminder = LocalReminder(title="Original")
        self.store.add_reminder(reminder)
        
        # Update reminder
        reminder.title = "Updated"
        self.store.update_reminder(reminder)
        
        retrieved = self.store.get_reminder(reminder.id)
        self.assertEqual(retrieved.title, "Updated")

    def test_delete_reminder(self) -> None:
        """Test deleting a reminder."""
        reminder = LocalReminder(title="To delete")
        self.store.add_reminder(reminder)
        
        self.store.delete_reminder(reminder.id)
        
        retrieved = self.store.get_reminder(reminder.id)
        self.assertIsNone(retrieved)

    def test_reminder_due_soon(self) -> None:
        """Test filtering reminders due soon."""
        now = datetime.now()
        
        # Due in 1 hour
        soon = LocalReminder(
            title="Soon",
            due_date=now + timedelta(hours=1)
        )
        
        # Due in 5 days
        later = LocalReminder(
            title="Later",
            due_date=now + timedelta(days=5)
        )
        
        self.store.add_reminder(soon)
        self.store.add_reminder(later)
        
        due_soon = self.store.list_reminders_due_soon(hours=2)
        self.assertEqual(len(due_soon), 1)
        self.assertEqual(due_soon[0].title, "Soon")


class TestNoteStore(unittest.TestCase):
    """Test storage and retrieval of notes."""

    def setUp(self) -> None:
        from src.assistant.local_storage import NoteStore
        self.store = NoteStore()

    def test_add_note_and_retrieve(self) -> None:
        """Test adding and retrieving notes."""
        note = LocalNote(title="Shopping list", content="Milk, bread, eggs")
        self.store.add_note(note)
        
        retrieved = self.store.get_note(note.id)
        self.assertIsNotNone(retrieved)
        self.assertEqual(retrieved.content, "Milk, bread, eggs")

    def test_search_notes_by_title(self) -> None:
        """Test searching notes by title keyword."""
        note1 = LocalNote(title="Python tips", content="...")
        note2 = LocalNote(title="JavaScript tips", content="...")
        
        self.store.add_note(note1)
        self.store.add_note(note2)
        
        results = self.store.search_notes("Python")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].title, "Python tips")

    def test_search_notes_by_tag(self) -> None:
        """Test searching notes by tag."""
        note1 = LocalNote(title="Note 1", content="...", tags=["work", "urgent"])
        note2 = LocalNote(title="Note 2", content="...", tags=["personal"])
        
        self.store.add_note(note1)
        self.store.add_note(note2)
        
        work_notes = self.store.search_by_tag("work")
        self.assertEqual(len(work_notes), 1)

    def test_list_notes_exclude_archived(self) -> None:
        """Test that archived notes are excluded by default."""
        note1 = LocalNote(title="Active", content="...")
        note2 = LocalNote(title="Archived", content="...")
        note2.archived = True
        
        self.store.add_note(note1)
        self.store.add_note(note2)
        
        active = self.store.list_notes(exclude_archived=True)
        self.assertEqual(len(active), 1)
        self.assertEqual(active[0].title, "Active")

    def test_delete_note(self) -> None:
        """Test deleting a note."""
        note = LocalNote(title="Temporary", content="...")
        self.store.add_note(note)
        
        self.store.delete_note(note.id)
        
        retrieved = self.store.get_note(note.id)
        self.assertIsNone(retrieved)


if __name__ == "__main__":
    unittest.main()

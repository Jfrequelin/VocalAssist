"""
Local storage module for reminders and notes.
Provides in-memory storage with persistence capabilities.
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Optional, Literal, cast
import logging

logger = logging.getLogger(__name__)


@dataclass
class LocalReminder:
    """Represents a local reminder."""

    title: str
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    created_at: datetime = field(default_factory=datetime.now)
    due_date: Optional[datetime] = None
    completed: bool = False
    priority: Literal["low", "medium", "high"] = "medium"
    description: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Convert reminder to dictionary for serialization."""
        return {
            "id": self.id,
            "title": self.title,
            "created_at": self.created_at.isoformat(),
            "due_date": self.due_date.isoformat() if self.due_date else None,
            "completed": self.completed,
            "priority": self.priority,
            "description": self.description,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> LocalReminder:
        """Create reminder from dictionary."""
        priority_raw = str(data.get("priority", "medium"))
        priority: Literal["low", "medium", "high"] = "medium"
        if priority_raw in {"low", "medium", "high"}:
            priority = cast(Literal["low", "medium", "high"], priority_raw)

        return cls(
            id=data["id"],
            title=data["title"],
            created_at=datetime.fromisoformat(data["created_at"]),
            due_date=datetime.fromisoformat(data["due_date"]) if data.get("due_date") else None,
            completed=data.get("completed", False),
            priority=priority,
            description=data.get("description", ""),
        )


@dataclass
class LocalNote:
    """Represents a local note."""

    title: str
    content: str
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    created_at: datetime = field(default_factory=datetime.now)
    modified_at: datetime = field(default_factory=datetime.now)
    tags: list[str] = field(default_factory=lambda: cast(list[str], []))
    archived: bool = False

    def to_dict(self) -> dict[str, Any]:
        """Convert note to dictionary for serialization."""
        return {
            "id": self.id,
            "title": self.title,
            "content": self.content,
            "created_at": self.created_at.isoformat(),
            "modified_at": self.modified_at.isoformat(),
            "tags": self.tags,
            "archived": self.archived,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> LocalNote:
        """Create note from dictionary."""
        return cls(
            id=data["id"],
            title=data["title"],
            content=data["content"],
            created_at=datetime.fromisoformat(data["created_at"]),
            modified_at=datetime.fromisoformat(data["modified_at"]),
            tags=cast(list[str], data.get("tags", [])),
            archived=data.get("archived", False),
        )


class ReminderStore:
    """In-memory storage for reminders with optional persistence."""

    def __init__(self, persist_path: Optional[Path] = None) -> None:
        """Initialize reminder store.

        Args:
            persist_path: Optional path to persist reminders to JSON file.
        """
        self.reminders: dict[str, LocalReminder] = {}
        self.persist_path = persist_path

        if persist_path and persist_path.exists():
            self._load_from_file()

    def add_reminder(self, reminder: LocalReminder) -> str:
        """Add a reminder to the store.

        Args:
            reminder: LocalReminder instance to add.

        Returns:
            The reminder ID.
        """
        self.reminders[reminder.id] = reminder
        self._persist()
        return reminder.id

    def get_reminder(self, reminder_id: str) -> Optional[LocalReminder]:
        """Get a reminder by ID.

        Args:
            reminder_id: The reminder ID.

        Returns:
            The LocalReminder or None if not found.
        """
        return self.reminders.get(reminder_id)

    def update_reminder(self, reminder: LocalReminder) -> None:
        """Update an existing reminder.

        Args:
            reminder: Updated LocalReminder instance.
        """
        if reminder.id in self.reminders:
            self.reminders[reminder.id] = reminder
            self._persist()

    def delete_reminder(self, reminder_id: str) -> bool:
        """Delete a reminder by ID.

        Args:
            reminder_id: The reminder ID.

        Returns:
            True if deleted, False if not found.
        """
        if reminder_id in self.reminders:
            del self.reminders[reminder_id]
            self._persist()
            return True
        return False

    def list_reminders(
        self,
        completed: Optional[bool] = None,
        priority: Optional[str] = None,
    ) -> list[LocalReminder]:
        """List reminders with optional filtering.

        Args:
            completed: Filter by completion status.
            priority: Filter by priority level.

        Returns:
            List of matching reminders.
        """
        results = list(self.reminders.values())

        if completed is not None:
            results = [r for r in results if r.completed == completed]

        if priority is not None:
            results = [r for r in results if r.priority == priority]

        # Sort by due date, then by priority
        priority_order = {"high": 0, "medium": 1, "low": 2}
        results.sort(
            key=lambda r: (
                r.due_date or datetime.max,
                priority_order.get(r.priority, 3)
            )
        )

        return results

    def list_reminders_due_soon(self, hours: int = 24) -> list[LocalReminder]:
        """List reminders due within the specified hours.

        Args:
            hours: Number of hours to look ahead.

        Returns:
            List of reminders due soon, sorted by due date.
        """
        now = datetime.now()
        cutoff = now + timedelta(hours=hours)

        due_soon = [
            r for r in self.reminders.values()
            if r.due_date and now <= r.due_date <= cutoff and not r.completed
        ]

        due_soon.sort(key=lambda r: r.due_date or datetime.max)
        return due_soon

    def _persist(self) -> None:
        """Persist reminders to file if persist_path is set."""
        if not self.persist_path:
            return

        try:
            self.persist_path.parent.mkdir(parents=True, exist_ok=True)
            data = [r.to_dict() for r in self.reminders.values()]
            with open(self.persist_path, "w") as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to persist reminders: {e}")

    def _load_from_file(self) -> None:
        """Load reminders from file."""
        if not self.persist_path or not self.persist_path.exists():
            return

        try:
            with open(self.persist_path, "r") as f:
                data = json.load(f)

            for item in data:
                reminder = LocalReminder.from_dict(item)
                self.reminders[reminder.id] = reminder
        except Exception as e:
            logger.error(f"Failed to load reminders: {e}")


class NoteStore:
    """In-memory storage for notes with optional persistence."""

    def __init__(self, persist_path: Optional[Path] = None) -> None:
        """Initialize note store.

        Args:
            persist_path: Optional path to persist notes to JSON file.
        """
        self.notes: dict[str, LocalNote] = {}
        self.persist_path = persist_path

        if persist_path and persist_path.exists():
            self._load_from_file()

    def add_note(self, note: LocalNote) -> str:
        """Add a note to the store.

        Args:
            note: LocalNote instance to add.

        Returns:
            The note ID.
        """
        self.notes[note.id] = note
        self._persist()
        return note.id

    def get_note(self, note_id: str) -> Optional[LocalNote]:
        """Get a note by ID.

        Args:
            note_id: The note ID.

        Returns:
            The LocalNote or None if not found.
        """
        return self.notes.get(note_id)

    def update_note(self, note: LocalNote) -> None:
        """Update an existing note.

        Args:
            note: Updated LocalNote instance.
        """
        if note.id in self.notes:
            note.modified_at = datetime.now()
            self.notes[note.id] = note
            self._persist()

    def delete_note(self, note_id: str) -> bool:
        """Delete a note by ID.

        Args:
            note_id: The note ID.

        Returns:
            True if deleted, False if not found.
        """
        if note_id in self.notes:
            del self.notes[note_id]
            self._persist()
            return True
        return False

    def list_notes(self, exclude_archived: bool = False) -> list[LocalNote]:
        """List all notes with optional filtering.

        Args:
            exclude_archived: Whether to exclude archived notes.

        Returns:
            List of notes, most recently modified first.
        """
        results = list(self.notes.values())

        if exclude_archived:
            results = [n for n in results if not n.archived]

        results.sort(key=lambda n: n.modified_at, reverse=True)
        return results

    def search_notes(self, query: str) -> list[LocalNote]:
        """Search notes by title and content.

        Args:
            query: Search query string.

        Returns:
            List of matching notes.
        """
        query_lower = query.lower()
        results = [
            n for n in self.notes.values()
            if query_lower in n.title.lower() or query_lower in n.content.lower()
        ]

        results.sort(key=lambda n: n.modified_at, reverse=True)
        return results

    def search_by_tag(self, tag: str) -> list[LocalNote]:
        """Find notes with a specific tag.

        Args:
            tag: The tag to search for.

        Returns:
            List of notes with the tag.
        """
        tag_lower = tag.lower()
        results = [
            n for n in self.notes.values()
            if any(t.lower() == tag_lower for t in n.tags)
        ]

        results.sort(key=lambda n: n.modified_at, reverse=True)
        return results

    def _persist(self) -> None:
        """Persist notes to file if persist_path is set."""
        if not self.persist_path:
            return

        try:
            self.persist_path.parent.mkdir(parents=True, exist_ok=True)
            data = [n.to_dict() for n in self.notes.values()]
            with open(self.persist_path, "w") as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to persist notes: {e}")

    def _load_from_file(self) -> None:
        """Load notes from file."""
        if not self.persist_path or not self.persist_path.exists():
            return

        try:
            with open(self.persist_path, "r") as f:
                data = json.load(f)

            for item in data:
                note = LocalNote.from_dict(item)
                self.notes[note.id] = note
        except Exception as e:
            logger.error(f"Failed to load notes: {e}")

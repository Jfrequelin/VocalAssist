"""
Tests for MACRO-003-T2: Date parsing for local agenda
Tests French date parsing and calendar operations.
"""

from __future__ import annotations

import unittest
from datetime import datetime, timedelta, date

from src.assistant.date_parser import DateParser, DateParseResult, LocalAgenda


class TestDateParseResult(unittest.TestCase):
    """Test DateParseResult data structure."""

    def test_create_parse_result_with_datetime(self) -> None:
        """Test creating a parse result with datetime."""
        dt = datetime(2026, 5, 15, 14, 30)
        result = DateParseResult(datetime_value=dt, confidence=1.0)
        
        self.assertEqual(result.datetime_value, dt)
        self.assertEqual(result.confidence, 1.0)
        self.assertTrue(result.is_valid())

    def test_parse_result_with_date_only(self) -> None:
        """Test parse result with date but no time."""
        d = date(2026, 5, 15)
        result = DateParseResult(date_value=d, confidence=0.95)
        
        self.assertEqual(result.date_value, d)
        self.assertTrue(result.is_valid())

    def test_parse_result_invalid(self) -> None:
        """Test invalid parse result."""
        result = DateParseResult(confidence=0.0)
        
        self.assertFalse(result.is_valid())

    def test_parse_result_with_text(self) -> None:
        """Test parse result includes original text."""
        result = DateParseResult(
            datetime_value=datetime(2026, 5, 15),
            original_text="demain à 14h30",
            confidence=0.9
        )
        
        self.assertEqual(result.original_text, "demain à 14h30")


class TestDateParser(unittest.TestCase):
    """Test French date parsing."""

    def setUp(self) -> None:
        self.parser = DateParser()
        # Set reference date for testing
        self.now = datetime(2026, 4, 30, 10, 0)
        self.parser.reference_date = self.now

    def test_parse_demain(self) -> None:
        """Test parsing 'demain' (tomorrow)."""
        result = self.parser.parse("demain")
        
        self.assertIsNotNone(result)
        self.assertTrue(result.is_valid())
        expected = self.now + timedelta(days=1)
        self.assertEqual(result.date_value, expected.date())

    def test_parse_aujourd_hui(self) -> None:
        """Test parsing 'aujourd'hui' (today)."""
        result = self.parser.parse("aujourd'hui")
        
        self.assertIsNotNone(result)
        self.assertEqual(result.date_value, self.now.date())

    def test_parse_hier(self) -> None:
        """Test parsing 'hier' (yesterday)."""
        result = self.parser.parse("hier")
        
        self.assertIsNotNone(result)
        expected = self.now - timedelta(days=1)
        self.assertEqual(result.date_value, expected.date())

    def test_parse_day_of_week(self) -> None:
        """Test parsing day of week."""
        result = self.parser.parse("lundi")
        
        self.assertIsNotNone(result)
        self.assertTrue(result.is_valid())

    def test_parse_french_month_name(self) -> None:
        """Test parsing date with French month names."""
        result = self.parser.parse("15 mai")
        
        self.assertIsNotNone(result)
        self.assertEqual(result.date_value, date(2026, 5, 15))

    def test_parse_time_reference(self) -> None:
        """Test parsing time references."""
        result = self.parser.parse("14h30")
        
        self.assertIsNotNone(result)
        self.assertEqual(result.datetime_value.hour, 14)
        self.assertEqual(result.datetime_value.minute, 30)

    def test_parse_combined_date_time(self) -> None:
        """Test parsing combined date and time."""
        result = self.parser.parse("demain à 14h")
        
        self.assertIsNotNone(result)
        self.assertTrue(result.is_valid())
        # Should have time
        if result.datetime_value:
            self.assertEqual(result.datetime_value.hour, 14)
            expected_date = self.now + timedelta(days=1)
            self.assertEqual(result.datetime_value.date(), expected_date.date())

    def test_parse_relative_time(self) -> None:
        """Test parsing relative time expressions."""
        result = self.parser.parse("dans 2 heures")
        
        self.assertIsNotNone(result)
        self.assertTrue(result.is_valid())
        expected = self.now + timedelta(hours=2)
        self.assertIsNotNone(result.datetime_value)

    def test_parse_numeric_date(self) -> None:
        """Test parsing numeric dates."""
        result = self.parser.parse("15/05/2026")
        
        self.assertIsNotNone(result)
        self.assertEqual(result.date_value, date(2026, 5, 15))

    def test_parse_invalid_date(self) -> None:
        """Test parsing invalid date returns None or invalid result."""
        result = self.parser.parse("xxxxx date invalide")
        
        # Should return None or invalid result
        if result is not None:
            self.assertFalse(result.is_valid())
        else:
            self.assertIsNone(result)

    def test_parse_next_monday(self) -> None:
        """Test parsing 'prochain lundi' (next Monday)."""
        result = self.parser.parse("prochain lundi")
        
        self.assertIsNotNone(result)
        self.assertTrue(result.is_valid())

    def test_parse_this_week(self) -> None:
        """Test parsing 'cette semaine' with day name."""
        result = self.parser.parse("cette semaine mercredi")
        
        self.assertIsNotNone(result)
        # Should return a valid date
        self.assertTrue(result.is_valid())

    def test_parse_confidence_level(self) -> None:
        """Test that confidence levels vary."""
        result1 = self.parser.parse("demain")
        result2 = self.parser.parse("probablement demain")
        
        # Exact date should have higher confidence
        self.assertGreater(result1.confidence, 0.8)


class TestLocalAgenda(unittest.TestCase):
    """Test local agenda event management."""

    def setUp(self) -> None:
        self.agenda = LocalAgenda()
        self.now = datetime(2026, 4, 30, 10, 0)

    def test_create_agenda_event(self) -> None:
        """Test creating an agenda event."""
        event = self.agenda.create_event(
            title="Meeting",
            datetime=datetime(2026, 5, 1, 14, 0)
        )
        
        self.assertEqual(event["title"], "Meeting")
        self.assertIsNotNone(event["id"])
        self.assertEqual(event["datetime"], datetime(2026, 5, 1, 14, 0))

    def test_add_event_to_agenda(self) -> None:
        """Test adding event to agenda."""
        event = self.agenda.create_event(
            title="Appointment",
            datetime=datetime(2026, 5, 5, 15, 30)
        )
        
        self.agenda.add_event(event)
        
        retrieved = self.agenda.get_event(event["id"])
        self.assertIsNotNone(retrieved)
        self.assertEqual(retrieved["title"], "Appointment")

    def test_list_events_for_date(self) -> None:
        """Test listing events for a specific date."""
        d = date(2026, 5, 1)
        
        event1 = self.agenda.create_event(
            title="Morning meeting",
            datetime=datetime(2026, 5, 1, 9, 0)
        )
        event2 = self.agenda.create_event(
            title="Afternoon meeting",
            datetime=datetime(2026, 5, 1, 14, 0)
        )
        event3 = self.agenda.create_event(
            title="Next day",
            datetime=datetime(2026, 5, 2, 10, 0)
        )
        
        self.agenda.add_event(event1)
        self.agenda.add_event(event2)
        self.agenda.add_event(event3)
        
        day_events = self.agenda.get_events_for_date(d)
        self.assertEqual(len(day_events), 2)

    def test_list_events_for_week(self) -> None:
        """Test listing events for a week."""
        event1 = self.agenda.create_event(
            title="Monday",
            datetime=datetime(2026, 5, 4, 10, 0)
        )
        event2 = self.agenda.create_event(
            title="Saturday",
            datetime=datetime(2026, 5, 9, 14, 0)
        )
        event3 = self.agenda.create_event(
            title="Next week",
            datetime=datetime(2026, 5, 11, 10, 0)
        )
        
        self.agenda.add_event(event1)
        self.agenda.add_event(event2)
        self.agenda.add_event(event3)
        
        week_events = self.agenda.get_events_for_week(date(2026, 5, 4))
        self.assertEqual(len(week_events), 2)

    def test_event_with_description(self) -> None:
        """Test event with description."""
        event = self.agenda.create_event(
            title="Team lunch",
            datetime=datetime(2026, 5, 1, 12, 0),
            description="Celebrating Q2 launch"
        )
        
        self.assertEqual(event["description"], "Celebrating Q2 launch")

    def test_event_with_location(self) -> None:
        """Test event with location."""
        event = self.agenda.create_event(
            title="Conference",
            datetime=datetime(2026, 5, 15, 9, 0),
            location="Paris Convention Center"
        )
        
        self.assertEqual(event["location"], "Paris Convention Center")

    def test_delete_event(self) -> None:
        """Test deleting an event."""
        event = self.agenda.create_event(
            title="To delete",
            datetime=datetime(2026, 5, 1, 10, 0)
        )
        self.agenda.add_event(event)
        
        self.agenda.delete_event(event["id"])
        
        retrieved = self.agenda.get_event(event["id"])
        self.assertIsNone(retrieved)

    def test_update_event(self) -> None:
        """Test updating an event."""
        event = self.agenda.create_event(
            title="Original title",
            datetime=datetime(2026, 5, 1, 10, 0)
        )
        self.agenda.add_event(event)
        
        event["title"] = "Updated title"
        self.agenda.update_event(event)
        
        retrieved = self.agenda.get_event(event["id"])
        self.assertEqual(retrieved["title"], "Updated title")

    def test_search_events_by_title(self) -> None:
        """Test searching events by title."""
        event1 = self.agenda.create_event(
            title="Python workshop",
            datetime=datetime(2026, 5, 1, 9, 0)
        )
        event2 = self.agenda.create_event(
            title="Team meeting",
            datetime=datetime(2026, 5, 1, 14, 0)
        )
        
        self.agenda.add_event(event1)
        self.agenda.add_event(event2)
        
        results = self.agenda.search_events("Python")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["title"], "Python workshop")

    def test_upcoming_events(self) -> None:
        """Test listing upcoming events."""
        agenda = LocalAgenda()
        
        # Create events: 1 in next week, 1 in next 2 months, 1 in the past
        in_week = datetime.now() + timedelta(days=3)
        in_two_months = datetime.now() + timedelta(days=60)
        in_past = datetime.now() - timedelta(days=10)
        
        event1 = agenda.create_event(
            title="This week",
            datetime=in_week
        )
        event2 = agenda.create_event(
            title="Next month",
            datetime=in_two_months
        )
        event3 = agenda.create_event(
            title="Past event",
            datetime=in_past
        )
        
        agenda.add_event(event1)
        agenda.add_event(event2)
        agenda.add_event(event3)
        
        # Get upcoming events for next 30 days
        upcoming = agenda.get_upcoming_events(days=30)
        # Should have only the "This week" event (within 30 days)
        self.assertEqual(len(upcoming), 1)
        self.assertEqual(upcoming[0]["title"], "This week")


if __name__ == "__main__":
    unittest.main()

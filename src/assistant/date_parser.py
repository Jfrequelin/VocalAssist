"""
Date parsing module for French calendar expressions.
Handles relative dates, day names, month names, and time expressions.
"""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, date
from typing import Optional
import logging

logger = logging.getLogger(__name__)

# French month names
FRENCH_MONTHS = {
    "janvier": 1, "février": 2, "mars": 3, "avril": 4,
    "mai": 5, "juin": 6, "juillet": 7, "août": 8,
    "septembre": 9, "octobre": 10, "novembre": 11, "décembre": 12,
}

# French day names (0 = Monday, 6 = Sunday)
FRENCH_DAYS = {
    "lundi": 0,
    "mardi": 1,
    "mercredi": 2,
    "jeudi": 3,
    "vendredi": 4,
    "samedi": 5,
    "dimanche": 6,
}

# Reverse mapping
MONTH_NUMBERS_TO_FRENCH = {v: k for k, v in FRENCH_MONTHS.items()}
DAY_NUMBERS_TO_FRENCH = {v: k for k, v in FRENCH_DAYS.items()}


@dataclass
class DateParseResult:
    """Result of parsing a date expression."""
    
    datetime_value: Optional[datetime] = None
    date_value: Optional[date] = None
    original_text: Optional[str] = None
    confidence: float = 0.5
    
    def is_valid(self) -> bool:
        """Check if the parse result is valid."""
        return self.confidence > 0.5 and (self.datetime_value is not None or self.date_value is not None)


class DateParser:
    """Parser for French date and time expressions."""
    
    def __init__(self, reference_date: Optional[datetime] = None) -> None:
        """Initialize the date parser.
        
        Args:
            reference_date: Reference datetime for relative calculations.
        """
        self.reference_date = reference_date or datetime.now()

    def parse(self, text: str) -> Optional[DateParseResult]:
        """Parse a French date/time expression.
        
        Args:
            text: The text to parse.
            
        Returns:
            DateParseResult if valid, None otherwise.
        """
        text_lower = text.strip().lower()
        
        # Try each parsing strategy
        strategies = [
            self._parse_absolute_expressions,
            self._parse_relative_expressions,
            self._parse_day_names,
            self._parse_time_expressions,
            self._parse_numeric_dates,
            self._parse_combined_expressions,
        ]
        
        for strategy in strategies:
            result = strategy(text_lower)
            if result and result.is_valid():
                result.original_text = text
                return result
        
        return None

    def _parse_absolute_expressions(self, text: str) -> Optional[DateParseResult]:
        """Parse absolute date expressions like 'today', 'tomorrow'."""
        
        if "aujourd'hui" in text or "aujourd hui" in text:
            return DateParseResult(
                date_value=self.reference_date.date(),
                confidence=1.0
            )
        
        if "demain" in text:
            tomorrow = self.reference_date + timedelta(days=1)
            return DateParseResult(
                date_value=tomorrow.date(),
                confidence=1.0
            )
        
        if "hier" in text:
            yesterday = self.reference_date - timedelta(days=1)
            return DateParseResult(
                date_value=yesterday.date(),
                confidence=1.0
            )
        
        return None

    def _parse_relative_expressions(self, text: str) -> Optional[DateParseResult]:
        """Parse relative time expressions like 'dans 2 heures'."""
        
        # "dans X heures"
        match = re.search(r'dans\s+(\d+)\s+heures?', text)
        if match:
            hours = int(match.group(1))
            dt = self.reference_date + timedelta(hours=hours)
            return DateParseResult(datetime_value=dt, confidence=0.95)
        
        # "dans X jours"
        match = re.search(r'dans\s+(\d+)\s+jours?', text)
        if match:
            days = int(match.group(1))
            dt = self.reference_date + timedelta(days=days)
            return DateParseResult(date_value=dt.date(), confidence=0.95)
        
        # "dans X minutes"
        match = re.search(r'dans\s+(\d+)\s+minutes?', text)
        if match:
            minutes = int(match.group(1))
            dt = self.reference_date + timedelta(minutes=minutes)
            return DateParseResult(datetime_value=dt, confidence=0.95)
        
        # "dans X semaines"
        match = re.search(r'dans\s+(\d+)\s+semaines?', text)
        if match:
            weeks = int(match.group(1))
            dt = self.reference_date + timedelta(weeks=weeks)
            return DateParseResult(date_value=dt.date(), confidence=0.95)
        
        return None

    def _parse_day_names(self, text: str) -> Optional[DateParseResult]:
        """Parse French day names."""
        
        # "prochain lundi" or "next Monday"
        for day_name, day_num in FRENCH_DAYS.items():
            pattern = rf'prochain\s+{day_name}'
            if re.search(pattern, text):
                target_date = self._get_next_weekday(day_num)
                return DateParseResult(date_value=target_date, confidence=0.9)
            
            # "cette semaine" + day
            pattern = rf'cette\s+semaine.*{day_name}'
            if re.search(pattern, text):
                target_date = self._get_weekday_this_week(day_num)
                return DateParseResult(date_value=target_date, confidence=0.85)
        
        # Just day name (this week)
        for day_name, day_num in FRENCH_DAYS.items():
            if day_name in text:
                target_date = self._get_next_weekday(day_num)
                return DateParseResult(date_value=target_date, confidence=0.8)
        
        return None

    def _parse_time_expressions(self, text: str) -> Optional[DateParseResult]:
        """Parse time expressions like '14h30' or '14:30'."""
        
        # 14h30 format
        match = re.search(r'(\d{1,2})[h:](\d{2})(?:\s*(?:am|pm))?', text)
        if match:
            hour = int(match.group(1))
            minute = int(match.group(2))
            
            # Start with reference date at the specified time
            dt = self.reference_date.replace(hour=hour, minute=minute, second=0, microsecond=0)
            
            return DateParseResult(datetime_value=dt, confidence=0.85)
        
        # 14h format
        match = re.search(r'(\d{1,2})[h]\b', text)
        if match:
            hour = int(match.group(1))
            dt = self.reference_date.replace(hour=hour, minute=0, second=0, microsecond=0)
            
            return DateParseResult(datetime_value=dt, confidence=0.8)
        
        return None

    def _parse_numeric_dates(self, text: str) -> Optional[DateParseResult]:
        """Parse numeric dates like '15/05/2026' or '15-05-2026'."""
        
        # DD/MM/YYYY
        match = re.search(r'(\d{1,2})[/-](\d{1,2})[/-](\d{4})', text)
        if match:
            day = int(match.group(1))
            month = int(match.group(2))
            year = int(match.group(3))
            
            try:
                d = date(year, month, day)
                return DateParseResult(date_value=d, confidence=0.95)
            except ValueError:
                return None
        
        return None

    def _parse_combined_expressions(self, text: str) -> Optional[DateParseResult]:
        """Parse combined date and time expressions."""
        
        # "demain à 14h30"
        if "demain" in text and "à" in text:
            tomorrow = self.reference_date + timedelta(days=1)
            
            match = re.search(r'(\d{1,2})[h:](\d{2})', text)
            if match:
                hour = int(match.group(1))
                minute = int(match.group(2))
                dt = tomorrow.replace(hour=hour, minute=minute, second=0, microsecond=0)
                return DateParseResult(datetime_value=dt, confidence=0.95)
            else:
                # Check for just hour like "demain à 14h"
                match = re.search(r'(\d{1,2})[h]\b', text)
                if match:
                    hour = int(match.group(1))
                    dt = tomorrow.replace(hour=hour, minute=0, second=0, microsecond=0)
                    return DateParseResult(datetime_value=dt, confidence=0.9)
                else:
                    return DateParseResult(date_value=tomorrow.date(), confidence=0.9)
        
        # "15 mai à 14h"
        for month_name, month_num in FRENCH_MONTHS.items():
            pattern = rf'(\d{{1,2}})\s+{month_name}(?:\s+(\d{{4}}))?'
            match = re.search(pattern, text)
            if match:
                day = int(match.group(1))
                year = int(match.group(2)) if match.group(2) else self.reference_date.year
                
                # Look for time
                time_match = re.search(r'(\d{1,2})[h:](\d{2})', text)
                if time_match:
                    hour = int(time_match.group(1))
                    minute = int(time_match.group(2))
                    try:
                        dt = datetime(year, month_num, day, hour, minute)
                        return DateParseResult(datetime_value=dt, confidence=0.95)
                    except ValueError:
                        return None
                else:
                    try:
                        d = date(year, month_num, day)
                        return DateParseResult(date_value=d, confidence=0.9)
                    except ValueError:
                        return None
        
        return None

    def _get_next_weekday(self, target_weekday: int) -> date:
        """Get the next occurrence of a weekday.
        
        Args:
            target_weekday: 0=Monday, 6=Sunday.
            
        Returns:
            The date of the next occurrence.
        """
        current_weekday = self.reference_date.weekday()
        days_ahead = target_weekday - current_weekday
        
        if days_ahead <= 0:
            days_ahead += 7
        
        return (self.reference_date + timedelta(days=days_ahead)).date()

    def _get_weekday_this_week(self, target_weekday: int) -> date:
        """Get a weekday in the current week.
        
        Args:
            target_weekday: 0=Monday, 6=Sunday.
            
        Returns:
            The date of the weekday in current week.
        """
        current_weekday = self.reference_date.weekday()
        days_diff = target_weekday - current_weekday
        
        return (self.reference_date + timedelta(days=days_diff)).date()


class LocalAgenda:
    """Local calendar/agenda management."""
    
    def __init__(self) -> None:
        """Initialize the local agenda."""
        self.events: dict[str, dict] = {}
        self.date_parser = DateParser()

    def create_event(
        self,
        title: str,
        datetime: datetime,
        description: str = "",
        location: str = "",
    ) -> dict:
        """Create a new agenda event.
        
        Args:
            title: Event title.
            datetime: Event datetime.
            description: Event description.
            location: Event location.
            
        Returns:
            Dictionary representing the event.
        """
        return {
            "id": str(uuid.uuid4()),
            "title": title,
            "datetime": datetime,
            "description": description,
            "location": location,
            "created_at": datetime.now(),
        }

    def add_event(self, event: dict) -> str:
        """Add event to agenda.
        
        Args:
            event: Event dictionary.
            
        Returns:
            Event ID.
        """
        self.events[event["id"]] = event
        return event["id"]

    def get_event(self, event_id: str) -> Optional[dict]:
        """Get event by ID.
        
        Args:
            event_id: The event ID.
            
        Returns:
            Event dictionary or None if not found.
        """
        return self.events.get(event_id)

    def update_event(self, event: dict) -> None:
        """Update an existing event.
        
        Args:
            event: Updated event dictionary.
        """
        if event["id"] in self.events:
            self.events[event["id"]] = event

    def delete_event(self, event_id: str) -> bool:
        """Delete event by ID.
        
        Args:
            event_id: The event ID.
            
        Returns:
            True if deleted, False if not found.
        """
        if event_id in self.events:
            del self.events[event_id]
            return True
        return False

    def get_events_for_date(self, d: date) -> list[dict]:
        """Get all events for a specific date.
        
        Args:
            d: The date.
            
        Returns:
            List of events for that date.
        """
        events = [
            e for e in self.events.values()
            if e["datetime"].date() == d
        ]
        events.sort(key=lambda e: e["datetime"])
        return events

    def get_events_for_week(self, d: date) -> list[dict]:
        """Get all events for the week containing the date.
        
        Args:
            d: A date in the week.
            
        Returns:
            List of events for that week.
        """
        # Monday is 0, Sunday is 6
        weekday = d.weekday()
        monday = d - timedelta(days=weekday)
        sunday = monday + timedelta(days=6)
        
        events = [
            e for e in self.events.values()
            if monday <= e["datetime"].date() <= sunday
        ]
        events.sort(key=lambda e: e["datetime"])
        return events

    def search_events(self, query: str) -> list[dict]:
        """Search events by title.
        
        Args:
            query: Search query.
            
        Returns:
            List of matching events.
        """
        query_lower = query.lower()
        results = [
            e for e in self.events.values()
            if query_lower in e["title"].lower()
        ]
        results.sort(key=lambda e: e["datetime"])
        return results

    def get_upcoming_events(self, days: int = 7) -> list[dict]:
        """Get upcoming events.
        
        Args:
            days: Number of days to look ahead.
            
        Returns:
            List of upcoming events.
        """
        now = datetime.now()
        cutoff = now + timedelta(days=days)
        
        events = [
            e for e in self.events.values()
            if now <= e["datetime"] <= cutoff
        ]
        events.sort(key=lambda e: e["datetime"])
        return events

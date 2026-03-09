from __future__ import annotations

import threading
from datetime import datetime
from typing import Any


class EventKitService:
    """Service layer wrapping Apple EventKit for calendar event operations."""

    _RECURRENCE_MAP = {
        "daily": 0,
        "weekly": 1,
        "monthly": 2,
        "yearly": 3,
    }

    _SPAN_MAP = {"this": 0, "future": 1}

    def __init__(self, event_store: Any = None, ek_module: Any = None) -> None:
        if ek_module is not None:
            self._ek = ek_module
        else:
            import EventKit

            self._ek = EventKit

        if event_store is not None:
            self._store = event_store
        else:
            self._store = self._ek.EKEventStore.alloc().init()
            self._request_access()

    def _request_access(self) -> None:
        """Request and verify calendar access permission."""
        event = threading.Event()
        result: dict[str, Any] = {}

        def callback(granted: bool, error: Any) -> None:
            result["granted"] = granted
            result["error"] = error
            event.set()

        self._store.requestAccessToEntityType_completion_(
            self._ek.EKEntityTypeEvent,
            callback,
        )
        if not event.wait(timeout=30):
            raise TimeoutError(
                "Timed out waiting for calendar access permission"
            )

        if not result.get("granted"):
            raise PermissionError(
                f"Calendar access not granted: {result.get('error')}"
            )

    def get_all_calendars(self) -> list[Any]:
        """Return all event calendars."""
        calendars = self._store.calendarsForEntityType_(
            self._ek.EKEntityTypeEvent
        )
        return list(calendars) if calendars else []

    def get_calendar_by_name(self, name: str) -> Any | None:
        """Find a specific calendar by name."""
        for cal in self.get_all_calendars():
            if cal.title() == name:
                return cal
        return None

    def create_calendar(self, name: str) -> Any:
        """Create a new event calendar."""
        default_cal = self._store.defaultCalendarForNewEvents()
        if default_cal is None:
            raise RuntimeError(
                "No default calendar for events. "
                "Ensure a Calendar account is configured in System Settings."
            )
        source = default_cal.source()
        calendar = self._ek.EKCalendar.calendarForEntityType_eventStore_(
            self._ek.EKEntityTypeEvent,
            self._store,
        )
        calendar.setTitle_(name)
        calendar.setSource_(source)
        success, error = self._store.saveCalendar_commit_error_(
            calendar, True, None
        )
        if not success:
            raise RuntimeError(f"Failed to create calendar: {error}")
        return calendar

    def get_events(
        self, calendar_name: str, start: datetime, end: datetime
    ) -> list[Any]:
        """Fetch events for a specific calendar in a date range."""
        calendar = self.get_calendar_by_name(calendar_name)
        if calendar is None:
            raise ValueError(f"Calendar '{calendar_name}' not found")
        ns_start = self._datetime_to_nsdate(start)
        ns_end = self._datetime_to_nsdate(end)
        predicate = self._store.predicateForEventsWithStart_end_calendars_(
            ns_start, ns_end, [calendar]
        )
        events = self._store.eventsMatchingPredicate_(predicate)
        return list(events) if events else []

    def get_all_events(
        self, start: datetime, end: datetime
    ) -> list[Any]:
        """Fetch events across all calendars in a date range."""
        calendars = self.get_all_calendars()
        if not calendars:
            return []
        ns_start = self._datetime_to_nsdate(start)
        ns_end = self._datetime_to_nsdate(end)
        predicate = self._store.predicateForEventsWithStart_end_calendars_(
            ns_start, ns_end, calendars
        )
        events = self._store.eventsMatchingPredicate_(predicate)
        return list(events) if events else []

    def create_event(
        self,
        title: str,
        start_date: datetime,
        end_date: datetime,
        calendar_name: str | None = None,
        is_all_day: bool = False,
        location: str | None = None,
        url: str | None = None,
        notes: str | None = None,
        recurrence: str | None = None,
    ) -> Any:
        """Create a calendar event."""
        event = self._ek.EKEvent.eventWithEventStore_(self._store)
        event.setTitle_(title)
        event.setStartDate_(self._datetime_to_nsdate(start_date))
        event.setEndDate_(self._datetime_to_nsdate(end_date))
        event.setAllDay_(is_all_day)

        if calendar_name is not None:
            calendar = self.get_calendar_by_name(calendar_name)
            if calendar is None:
                raise ValueError(f"Calendar '{calendar_name}' not found")
            event.setCalendar_(calendar)
        else:
            default_cal = self._store.defaultCalendarForNewEvents()
            if default_cal is None:
                raise RuntimeError(
                    "No default calendar for events. "
                    "Ensure a Calendar account is configured in System Settings."
                )
            event.setCalendar_(default_cal)

        if location is not None:
            event.setLocation_(location)

        if url is not None:
            ns_url = self._make_nsurl(url)
            event.setURL_(ns_url)

        if notes is not None:
            event.setNotes_(notes)

        if recurrence:
            rule = self._create_recurrence_rule(recurrence)
            event.addRecurrenceRule_(rule)

        success, error = self._store.saveEvent_span_commit_error_(
            event, 0, True, None
        )
        if not success:
            raise RuntimeError(f"Failed to create event: {error}")
        return event

    def update_event(
        self,
        event_id: str,
        title: str | None = None,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
        is_all_day: bool | None = None,
        location: str | None = None,
        url: str | None = None,
        notes: str | None = None,
    ) -> Any:
        """Update an existing event. Only provided fields are changed."""
        event = self._find_event_by_id(event_id)
        if event is None:
            raise ValueError(f"Event '{event_id}' not found")

        if title is not None:
            event.setTitle_(title)
        if start_date is not None:
            event.setStartDate_(self._datetime_to_nsdate(start_date))
        if end_date is not None:
            event.setEndDate_(self._datetime_to_nsdate(end_date))
        if is_all_day is not None:
            event.setAllDay_(is_all_day)
        if location is not None:
            event.setLocation_(location)
        if url is not None:
            ns_url = self._make_nsurl(url)
            event.setURL_(ns_url)
        if notes is not None:
            event.setNotes_(notes)

        success, error = self._store.saveEvent_span_commit_error_(
            event, 0, True, None
        )
        if not success:
            raise RuntimeError(f"Failed to update event: {error}")
        return event

    def delete_event(self, event_id: str, span: str = "this") -> None:
        """Delete an event. span='this' or 'future' for recurring events."""
        event = self._find_event_by_id(event_id)
        if event is None:
            raise ValueError(f"Event '{event_id}' not found")

        span_value = self._SPAN_MAP.get(span)
        if span_value is None:
            raise ValueError(
                f"Invalid span '{span}'. Must be one of: this, future"
            )

        success, error = self._store.removeEvent_span_commit_error_(
            event, span_value, True, None
        )
        if not success:
            raise RuntimeError(f"Failed to delete event: {error}")

    def move_event(self, event_id: str, target_calendar_name: str) -> Any:
        """Move an event to a different calendar."""
        event = self._find_event_by_id(event_id)
        if event is None:
            raise ValueError(f"Event '{event_id}' not found")

        calendar = self.get_calendar_by_name(target_calendar_name)
        if calendar is None:
            raise ValueError(f"Calendar '{target_calendar_name}' not found")

        event.setCalendar_(calendar)
        success, error = self._store.saveEvent_span_commit_error_(
            event, 0, True, None
        )
        if not success:
            raise RuntimeError(f"Failed to move event: {error}")
        return event

    def _find_event_by_id(self, event_id: str) -> Any | None:
        """Look up an event by its calendarItemIdentifier."""
        return self._store.calendarItemWithIdentifier_(event_id)

    def _datetime_to_nsdate(self, dt: datetime) -> Any:
        """Convert a Python datetime to NSDate."""
        import Foundation

        timestamp = dt.timestamp()
        return Foundation.NSDate.dateWithTimeIntervalSince1970_(timestamp)

    def _nsdate_to_datetime(self, nsdate: Any) -> datetime:
        """Convert an NSDate to a Python datetime."""
        timestamp = nsdate.timeIntervalSince1970()
        return datetime.fromtimestamp(timestamp)

    def _make_nsurl(self, url_string: str) -> Any:
        """Create an NSURL from a string."""
        import Foundation

        return Foundation.NSURL.URLWithString_(url_string)

    def _create_recurrence_rule(self, recurrence: str) -> Any:
        """Create an EKRecurrenceRule from a recurrence string."""
        freq = self._RECURRENCE_MAP.get(recurrence.lower())
        if freq is None:
            raise ValueError(
                f"Invalid recurrence '{recurrence}'. "
                f"Must be one of: daily, weekly, monthly, yearly"
            )
        rule = (
            self._ek.EKRecurrenceRule.alloc()
            .initRecurrenceWithFrequency_interval_end_(freq, 1, None)
        )
        return rule

from __future__ import annotations

import threading
from datetime import datetime, timedelta
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

    _AVAILABILITY_MAP = {
        "busy": 0,
        "free": 1,
        "tentative": 2,
        "unavailable": 3,
    }

    _WEEKDAY_MAP = {
        "sunday": 1,
        "monday": 2,
        "tuesday": 3,
        "wednesday": 4,
        "thursday": 5,
        "friday": 6,
        "saturday": 7,
    }

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

    def get_calendar_by_id(self, calendar_id: str) -> Any | None:
        """Find a specific calendar by its identifier."""
        for cal in self.get_all_calendars():
            if cal.calendarIdentifier() == calendar_id:
                return cal
        return None

    def _resolve_calendar(
        self,
        name: str | None = None,
        calendar_id: str | None = None,
    ) -> Any:
        """Resolve a calendar by ID (preferred) or name.

        When both are provided, resolves by ID and validates that the
        calendar's title matches the given name.

        Raises ValueError if the calendar cannot be found, the name/ID
        mismatch, or neither identifier is provided.
        """
        if calendar_id is not None:
            cal = self.get_calendar_by_id(calendar_id)
            if cal is None:
                raise ValueError(
                    f"Calendar with id '{calendar_id}' not found"
                )
            if name is not None and cal.title() != name:
                raise ValueError(
                    f"Calendar id '{calendar_id}' resolves to "
                    f"'{cal.title()}', not '{name}'"
                )
            return cal
        if name is not None:
            cal = self.get_calendar_by_name(name)
            if cal is None:
                raise ValueError(f"Calendar '{name}' not found")
            return cal
        raise ValueError(
            "Either calendar name or calendar_id must be provided"
        )

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
        self,
        calendar_name: str | None,
        start: datetime,
        end: datetime,
        *,
        calendar_id: str | None = None,
    ) -> list[Any]:
        """Fetch events for a specific calendar in a date range."""
        calendar = self._resolve_calendar(
            name=calendar_name, calendar_id=calendar_id
        )
        ns_start = self._datetime_to_nsdate(start)
        ns_end = self._datetime_to_nsdate(end)
        predicate = self._store.predicateForEventsWithStartDate_endDate_calendars_(
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
        predicate = self._store.predicateForEventsWithStartDate_endDate_calendars_(
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
        recurrence: str | dict | None = None,
        calendar_id: str | None = None,
        availability: str | None = None,
        time_zone: str | None = None,
        alarm_minutes_before: list[int] | None = None,
    ) -> Any:
        """Create a calendar event."""
        event = self._ek.EKEvent.eventWithEventStore_(self._store)
        event.setTitle_(title)
        event.setStartDate_(self._datetime_to_nsdate(start_date))
        event.setEndDate_(self._datetime_to_nsdate(end_date))
        event.setAllDay_(is_all_day)

        if calendar_name is not None or calendar_id is not None:
            calendar = self._resolve_calendar(
                name=calendar_name, calendar_id=calendar_id
            )
            event.setCalendar_(calendar)
        else:
            default_cal = self._store.defaultCalendarForNewEvents()
            if default_cal is None:
                raise RuntimeError(
                    "No default calendar for events. "
                    "Ensure a Calendar account is configured in System Settings."
                )
            event.setCalendar_(default_cal)

        if location:
            event.setLocation_(location)

        if url:
            ns_url = self._make_nsurl(url)
            event.setURL_(ns_url)

        if notes:
            event.setNotes_(notes)

        if availability is not None:
            event.setAvailability_(self._availability_value(availability))

        if time_zone:
            event.setTimeZone_(self._make_nstimezone(time_zone))

        if alarm_minutes_before is not None:
            event.setAlarms_(self._make_alarms(alarm_minutes_before) or None)

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
        availability: str | None = None,
        time_zone: str | None = None,
        alarm_minutes_before: list[int] | None = None,
        recurrence: str | dict | None = None,
        span: str = "this",
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
            event.setLocation_(location or None)
        if url is not None:
            if url:
                ns_url = self._make_nsurl(url)
                event.setURL_(ns_url)
            else:
                event.setURL_(None)
        if notes is not None:
            event.setNotes_(notes or None)
        if availability is not None:
            event.setAvailability_(self._availability_value(availability))
        if time_zone is not None:
            event.setTimeZone_(
                self._make_nstimezone(time_zone) if time_zone else None
            )
        if alarm_minutes_before is not None:
            event.setAlarms_(self._make_alarms(alarm_minutes_before) or None)
        if recurrence is not None:
            event.setRecurrenceRules_(
                [self._create_recurrence_rule(recurrence)]
                if recurrence
                else None
            )

        span_value = self._span_value(span)
        success, error = self._store.saveEvent_span_commit_error_(
            event, span_value, True, None
        )
        if not success:
            raise RuntimeError(f"Failed to update event: {error}")
        return event

    def delete_event(self, event_id: str, span: str = "this") -> None:
        """Delete an event. span='this' or 'future' for recurring events."""
        event = self._find_event_by_id(event_id)
        if event is None:
            raise ValueError(f"Event '{event_id}' not found")

        span_value = self._span_value(span)

        success, error = self._store.removeEvent_span_commit_error_(
            event, span_value, True, None
        )
        if not success:
            raise RuntimeError(f"Failed to delete event: {error}")

    def move_event(
        self,
        event_id: str,
        target_calendar_name: str | None = None,
        *,
        target_calendar_id: str | None = None,
    ) -> Any:
        """Move an event to a different calendar."""
        event = self._find_event_by_id(event_id)
        if event is None:
            raise ValueError(f"Event '{event_id}' not found")

        calendar = self._resolve_calendar(
            name=target_calendar_name, calendar_id=target_calendar_id
        )

        event.setCalendar_(calendar)
        success, error = self._store.saveEvent_span_commit_error_(
            event, 0, True, None
        )
        if not success:
            raise RuntimeError(f"Failed to move event: {error}")
        return event

    def _span_value(self, span: str) -> int:
        """Map a span name to its EKSpan value."""
        value = self._SPAN_MAP.get(span)
        if value is None:
            raise ValueError(
                f"Invalid span '{span}'. Must be one of: this, future"
            )
        return value

    def _find_event_by_id(self, event_id: str) -> Any | None:
        """Look up an event, resolving a '<series-id>/<occurrence>' suffix.

        Every occurrence of a recurring series shares one
        calendarItemIdentifier, and the store returns the first occurrence for
        it, so an occurrence has to be located through a date predicate.
        """
        series_id, separator, occurrence = event_id.partition("/")
        event = self._store.calendarItemWithIdentifier_(series_id)
        if not separator or event is None:
            return event

        target = datetime.fromisoformat(occurrence)
        calendar = event.calendar()
        predicate = self._store.predicateForEventsWithStartDate_endDate_calendars_(
            self._datetime_to_nsdate(target - timedelta(days=1)),
            self._datetime_to_nsdate(target + timedelta(days=1)),
            [calendar] if calendar else None,
        )
        for candidate in self._store.eventsMatchingPredicate_(predicate) or []:
            if candidate.calendarItemIdentifier() != series_id:
                continue
            candidate_date = candidate.occurrenceDate()
            if candidate_date is None:
                continue
            delta = candidate_date.timeIntervalSince1970() - target.timestamp()
            if abs(delta) < 1:
                return candidate

        raise ValueError(f"Occurrence '{event_id}' not found")

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

        ns_url = Foundation.NSURL.URLWithString_(url_string)
        if ns_url is None:
            raise ValueError(f"Invalid URL: {url_string}")
        return ns_url

    def _create_recurrence_rule(self, recurrence: str | dict) -> Any:
        """Create an EKRecurrenceRule from a frequency string or a spec dict."""
        spec = (
            {"frequency": recurrence}
            if isinstance(recurrence, str)
            else recurrence
        )

        frequency = spec.get("frequency")
        if not isinstance(frequency, str):
            raise ValueError("Recurrence requires a 'frequency'")
        freq = self._RECURRENCE_MAP.get(frequency.lower())
        if freq is None:
            raise ValueError(
                f"Invalid recurrence '{frequency}'. "
                f"Must be one of: daily, weekly, monthly, yearly"
            )

        end_date = spec.get("end_date")
        count = spec.get("count")
        if end_date is not None and count is not None:
            raise ValueError(
                "Recurrence accepts 'end_date' or 'count', not both"
            )
        end = None
        if end_date is not None:
            end = self._ek.EKRecurrenceEnd.recurrenceEndWithEndDate_(
                self._datetime_to_nsdate(datetime.fromisoformat(end_date))
            )
        elif count is not None:
            end = self._ek.EKRecurrenceEnd.recurrenceEndWithOccurrenceCount_(
                count
            )

        days_of_week = None
        days = spec.get("days_of_week")
        if days:
            days_of_week = [
                self._ek.EKRecurrenceDayOfWeek.dayOfWeek_(
                    self._weekday_value(day)
                )
                for day in days
            ]

        return (
            self._ek.EKRecurrenceRule.alloc()
            .initRecurrenceWithFrequency_interval_daysOfTheWeek_daysOfTheMonth_monthsOfTheYear_weeksOfTheYear_daysOfTheYear_setPositions_end_(
                freq,
                spec.get("interval", 1),
                days_of_week,
                None,
                None,
                None,
                None,
                None,
                end,
            )
        )

    def _weekday_value(self, day: str) -> int:
        """Map a weekday name to its EKWeekday value."""
        value = self._WEEKDAY_MAP.get(day.lower())
        if value is None:
            raise ValueError(
                f"Invalid weekday '{day}'. Must be one of: "
                f"{', '.join(self._WEEKDAY_MAP)}"
            )
        return value

    def _make_nstimezone(self, name: str) -> Any:
        """Create an NSTimeZone from an IANA time zone name."""
        import Foundation

        time_zone = Foundation.NSTimeZone.timeZoneWithName_(name)
        if time_zone is None:
            raise ValueError(f"Invalid time zone: {name}")
        return time_zone

    def _availability_value(self, availability: str) -> int:
        """Map an availability name to its EKEventAvailability value."""
        value = self._AVAILABILITY_MAP.get(availability.lower())
        if value is None:
            raise ValueError(
                f"Invalid availability '{availability}'. Must be one of: "
                f"{', '.join(self._AVAILABILITY_MAP)}"
            )
        return value

    def _make_alarms(self, minutes_before: list[int]) -> list[Any]:
        """Create EKAlarms firing the given number of minutes before an event."""
        return [
            self._ek.EKAlarm.alarmWithRelativeOffset_(-minutes * 60)
            for minutes in minutes_before
        ]

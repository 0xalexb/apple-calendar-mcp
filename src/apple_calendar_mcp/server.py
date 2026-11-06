from __future__ import annotations

import threading
from importlib.metadata import version

from mcp.server import MCPServer

from apple_calendar_mcp import operations
from apple_calendar_mcp.eventkit_service import EventKitService

mcp = MCPServer("apple-calendar", version=version("apple-calendar-mcp"))

_service: EventKitService | None = None
_service_lock = threading.Lock()


def _get_service() -> EventKitService:
    global _service
    with _service_lock:
        if _service is None:
            _service = EventKitService()
        return _service


@mcp.tool()
def ping() -> str:
    """Health check - returns pong."""
    return "pong"


@mcp.tool()
def list_calendars() -> list[dict]:
    """Returns all calendar names with their upcoming event count (next 30 days)."""
    return operations.list_calendars(_get_service())


@mcp.tool()
def get_events(
    start_date: str,
    calendar_name: str | None = None,
    end_date: str | None = None,
    calendar_id: str | None = None,
) -> list[dict]:
    """Returns events for a specific calendar in a date range. Dates in ISO 8601 format. If end_date is omitted, defaults to start + 1 day. Provide calendar_name, calendar_id (preferred, stable across renames), or both."""
    return operations.get_events(
        _get_service(),
        start_date=start_date,
        calendar_name=calendar_name,
        end_date=end_date,
        calendar_id=calendar_id,
    )


@mcp.tool()
def get_all_events(
    start_date: str,
    end_date: str | None = None,
) -> dict:
    """Returns all events grouped by calendar. Dates in ISO 8601 format. If end_date is omitted, defaults to start + 1 day."""
    return operations.get_all_events(
        _get_service(),
        start_date=start_date,
        end_date=end_date,
    )


@mcp.tool()
def create_calendar(name: str) -> dict:
    """Creates a new calendar."""
    return operations.create_calendar(
        _get_service(),
        name=name,
    )


@mcp.tool()
def create_event(
    title: str,
    start_date: str,
    end_date: str | None = None,
    calendar_name: str | None = None,
    calendar_id: str | None = None,
    is_all_day: bool = False,
    location: str | None = None,
    url: str | None = None,
    notes: str | None = None,
    recurrence: str | dict | None = None,
    availability: str | None = None,
    time_zone: str | None = None,
    alarm_minutes_before: list[int] | None = None,
) -> dict:
    """Creates a calendar event. start_date in ISO 8601 format. If end_date is omitted, defaults to start + 1 hour (or +1 day if all-day). Optional: calendar_name or calendar_id (preferred, avoids ambiguity), is_all_day, location, url, notes, availability (busy/free/tentative/unavailable), time_zone (IANA name, e.g. Europe/Berlin), alarm_minutes_before (e.g. [10, 60] for reminders 10 and 60 minutes ahead). recurrence is either a frequency string (daily/weekly/monthly/yearly) or an object {"frequency": required, "interval": every N periods, "days_of_week": ["monday", ...], "end_date": ISO date, "count": number of occurrences} — end_date and count are mutually exclusive. Those five keys are the only ones accepted: any other key is an error, including the end, days_of_month, months_of_year and week_positions that get_events prints in recurrence_rules, so that read shape does not round-trip. {} is an error. Omit recurrence, or pass "", for a non-recurring event."""
    return operations.create_event(
        _get_service(),
        title=title,
        start_date=start_date,
        end_date=end_date,
        calendar_name=calendar_name,
        calendar_id=calendar_id,
        is_all_day=is_all_day,
        location=location,
        url=url,
        notes=notes,
        recurrence=recurrence,
        availability=availability,
        time_zone=time_zone,
        alarm_minutes_before=alarm_minutes_before,
    )


@mcp.tool()
def update_event(
    event_id: str,
    title: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    is_all_day: bool | None = None,
    location: str | None = None,
    url: str | None = None,
    notes: str | None = None,
    availability: str | None = None,
    time_zone: str | None = None,
    alarm_minutes_before: list[int] | None = None,
    recurrence: str | dict | None = None,
    span: str = "this",
) -> dict:
    """Updates an existing event. Only provided fields are changed. Dates in ISO 8601 format. availability is busy/free/tentative/unavailable, time_zone an IANA name, alarm_minutes_before a list like [10, 60] ([] clears alarms). recurrence takes a frequency string or the object described by create_event, with the same rules: an unknown key is an error, {} is an error, and only "" clears the recurrence. For recurring events, span='this' (default) changes only this occurrence, span='future' changes this and all future ones."""
    return operations.update_event(
        _get_service(),
        event_id=event_id,
        title=title,
        start_date=start_date,
        end_date=end_date,
        is_all_day=is_all_day,
        location=location,
        url=url,
        notes=notes,
        availability=availability,
        time_zone=time_zone,
        alarm_minutes_before=alarm_minutes_before,
        recurrence=recurrence,
        span=span,
    )


@mcp.tool()
def delete_event(event_id: str, span: str = "this") -> dict:
    """Deletes an event. For recurring events, span='this' (default) deletes only this occurrence, span='future' deletes this and all future occurrences."""
    return operations.delete_event(
        _get_service(),
        event_id=event_id,
        span=span,
    )


@mcp.tool()
def move_event(
    event_id: str,
    target_calendar_name: str | None = None,
    target_calendar_id: str | None = None,
) -> dict:
    """Moves an event to a different calendar. Provide target_calendar_name, target_calendar_id (preferred, stable across renames), or both."""
    return operations.move_event(
        _get_service(),
        event_id=event_id,
        target_calendar_name=target_calendar_name,
        target_calendar_id=target_calendar_id,
    )


@mcp.tool()
def quick_add(title: str, start_date: str, notes: str | None = None) -> dict:
    """Quickly creates an event in the default calendar. start_date in ISO 8601 format. Defaults to 1-hour duration."""
    return operations.quick_add(
        _get_service(),
        title=title,
        start_date=start_date,
        notes=notes,
    )


def main():
    import sys

    if len(sys.argv) > 1 and sys.argv[1] in ("--version", "-V"):
        print(f"apple-calendar-mcp {version('apple-calendar-mcp')}")
        sys.exit(0)
    mcp.run()


if __name__ == "__main__":
    main()

from __future__ import annotations

import threading
from datetime import datetime, timedelta

from mcp.server.fastmcp import FastMCP

from apple_calendar_mcp.eventkit_service import EventKitService

mcp = FastMCP("apple-calendar")

_service: EventKitService | None = None
_service_lock = threading.Lock()


def _get_service() -> EventKitService:
    global _service
    with _service_lock:
        if _service is None:
            _service = EventKitService()
        return _service


def _format_nsdate(nsdate) -> str | None:
    if nsdate is None:
        return None
    timestamp = nsdate.timeIntervalSince1970()
    dt = datetime.fromtimestamp(timestamp)
    return dt.isoformat()


def _format_event(event) -> dict:
    return {
        "id": event.calendarItemIdentifier(),
        "title": event.title(),
        "start_date": _format_nsdate(event.startDate()),
        "end_date": _format_nsdate(event.endDate()),
        "is_all_day": bool(event.isAllDay()),
        "location": event.location(),
        "url": str(event.URL()) if event.URL() else None,
        "notes": event.notes(),
        "calendar": event.calendar().title() if event.calendar() else None,
        "calendar_id": event.calendar().calendarIdentifier() if event.calendar() else None,
        "has_recurrence": bool(event.hasRecurrenceRules()),
    }


@mcp.tool()
def ping() -> str:
    """Health check - returns pong."""
    return "pong"


@mcp.tool()
def list_calendars() -> list[dict]:
    """Returns all calendar names with their upcoming event count (next 30 days)."""
    service = _get_service()
    calendars = service.get_all_calendars()
    now = datetime.now()
    end = now + timedelta(days=30)
    all_events = service.get_all_events(now, end)
    counts: dict[str, int] = {}
    for ev in all_events:
        cal = ev.calendar()
        if cal:
            cal_id = cal.calendarIdentifier()
            counts[cal_id] = counts.get(cal_id, 0) + 1
    return [
        {
            "id": cal.calendarIdentifier(),
            "name": cal.title(),
            "upcoming_event_count": counts.get(cal.calendarIdentifier(), 0),
        }
        for cal in calendars
    ]


@mcp.tool()
def get_events(
    start_date: str,
    calendar_name: str | None = None,
    end_date: str | None = None,
    calendar_id: str | None = None,
) -> list[dict]:
    """Returns events for a specific calendar in a date range. Dates in ISO 8601 format. If end_date is omitted, defaults to start + 1 day. Provide calendar_name, calendar_id (preferred, stable across renames), or both."""
    service = _get_service()
    start = datetime.fromisoformat(start_date)
    end = datetime.fromisoformat(end_date) if end_date else start + timedelta(days=1)
    events = service.get_events(
        calendar_name, start, end, calendar_id=calendar_id
    )
    return [_format_event(ev) for ev in events]


@mcp.tool()
def get_all_events(
    start_date: str,
    end_date: str | None = None,
) -> dict:
    """Returns all events grouped by calendar. Dates in ISO 8601 format. If end_date is omitted, defaults to start + 1 day."""
    service = _get_service()
    start = datetime.fromisoformat(start_date)
    end = datetime.fromisoformat(end_date) if end_date else start + timedelta(days=1)
    events = service.get_all_events(start, end)
    grouped: dict[str, list[dict]] = {}
    for ev in events:
        cal = ev.calendar()
        key = cal.title() if cal else "Unknown"
        if key not in grouped:
            grouped[key] = []
        grouped[key].append(_format_event(ev))
    return grouped


@mcp.tool()
def create_calendar(name: str) -> dict:
    """Creates a new calendar."""
    service = _get_service()
    cal = service.create_calendar(name)
    return {"name": cal.title(), "created": True}


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
    recurrence: str | None = None,
) -> dict:
    """Creates a calendar event. start_date in ISO 8601 format. If end_date is omitted, defaults to start + 1 hour (or +1 day if all-day). Optional: calendar_name or calendar_id (preferred, avoids ambiguity), is_all_day, location, url, notes, recurrence (daily/weekly/monthly/yearly)."""
    service = _get_service()
    start = datetime.fromisoformat(start_date)
    if end_date:
        end = datetime.fromisoformat(end_date)
    elif is_all_day:
        end = start + timedelta(days=1)
    else:
        end = start + timedelta(hours=1)
    event = service.create_event(
        title=title,
        start_date=start,
        end_date=end,
        calendar_name=calendar_name,
        calendar_id=calendar_id,
        is_all_day=is_all_day,
        location=location,
        url=url,
        notes=notes,
        recurrence=recurrence,
    )
    return _format_event(event)


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
) -> dict:
    """Updates an existing event. Only provided fields are changed. Dates in ISO 8601 format."""
    service = _get_service()
    parsed_start = datetime.fromisoformat(start_date) if start_date else None
    parsed_end = datetime.fromisoformat(end_date) if end_date else None
    event = service.update_event(
        event_id,
        title=title,
        start_date=parsed_start,
        end_date=parsed_end,
        is_all_day=is_all_day,
        location=location,
        url=url,
        notes=notes,
    )
    return _format_event(event)


@mcp.tool()
def delete_event(event_id: str, span: str = "this") -> dict:
    """Deletes an event. For recurring events, span='this' (default) deletes only this occurrence, span='future' deletes this and all future occurrences."""
    service = _get_service()
    service.delete_event(event_id, span=span)
    return {"id": event_id, "deleted": True}


@mcp.tool()
def move_event(
    event_id: str,
    target_calendar_name: str | None = None,
    target_calendar_id: str | None = None,
) -> dict:
    """Moves an event to a different calendar. Provide target_calendar_name, target_calendar_id (preferred, stable across renames), or both."""
    service = _get_service()
    event = service.move_event(
        event_id,
        target_calendar_name,
        target_calendar_id=target_calendar_id,
    )
    return _format_event(event)


@mcp.tool()
def quick_add(title: str, start_date: str, notes: str | None = None) -> dict:
    """Quickly creates an event in the default calendar. start_date in ISO 8601 format. Defaults to 1-hour duration."""
    service = _get_service()
    start = datetime.fromisoformat(start_date)
    end = start + timedelta(hours=1)
    event = service.create_event(
        title=title,
        start_date=start,
        end_date=end,
        notes=notes,
    )
    return _format_event(event)


def main():
    import sys

    if len(sys.argv) > 1 and sys.argv[1] in ("--version", "-V"):
        from importlib.metadata import version

        print(f"apple-calendar-mcp {version('apple-calendar-mcp')}")
        sys.exit(0)
    mcp.run()


if __name__ == "__main__":
    main()

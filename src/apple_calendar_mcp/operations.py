from __future__ import annotations

from datetime import datetime, timedelta
from typing import TYPE_CHECKING

from apple_calendar_mcp.formatting import _format_calendar, _format_event

if TYPE_CHECKING:
    from apple_calendar_mcp.eventkit_service import EventKitService


def list_calendars(service: EventKitService) -> list[dict]:
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
            **_format_calendar(cal),
            "upcoming_event_count": counts.get(cal.calendarIdentifier(), 0),
        }
        for cal in calendars
    ]


def get_events(
    service: EventKitService,
    start_date: str,
    calendar_name: str | None = None,
    end_date: str | None = None,
    calendar_id: str | None = None,
) -> list[dict]:
    start = datetime.fromisoformat(start_date)
    end = datetime.fromisoformat(end_date) if end_date else start + timedelta(days=1)
    events = service.get_events(
        calendar_name, start, end, calendar_id=calendar_id
    )
    return [_format_event(ev) for ev in events]


def get_all_events(
    service: EventKitService,
    start_date: str,
    end_date: str | None = None,
) -> dict:
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


def create_calendar(service: EventKitService, name: str) -> dict:
    cal = service.create_calendar(name)
    return {"name": cal.title(), "created": True}


def create_event(
    service: EventKitService,
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
        availability=availability,
        time_zone=time_zone,
        alarm_minutes_before=alarm_minutes_before,
    )
    return _format_event(event)


def update_event(
    service: EventKitService,
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
        availability=availability,
        time_zone=time_zone,
        alarm_minutes_before=alarm_minutes_before,
        recurrence=recurrence,
        span=span,
    )
    return _format_event(event)


def delete_event(
    service: EventKitService, event_id: str, span: str = "this"
) -> dict:
    service.delete_event(event_id, span=span)
    return {"id": event_id, "deleted": True}


def move_event(
    service: EventKitService,
    event_id: str,
    target_calendar_name: str | None = None,
    target_calendar_id: str | None = None,
) -> dict:
    event = service.move_event(
        event_id,
        target_calendar_name,
        target_calendar_id=target_calendar_id,
    )
    return _format_event(event)


def quick_add(
    service: EventKitService,
    title: str,
    start_date: str,
    notes: str | None = None,
) -> dict:
    start = datetime.fromisoformat(start_date)
    end = start + timedelta(hours=1)
    event = service.create_event(
        title=title,
        start_date=start,
        end_date=end,
        notes=notes,
    )
    return _format_event(event)

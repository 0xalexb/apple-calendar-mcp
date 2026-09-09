from __future__ import annotations

import threading
from datetime import datetime, timedelta
from importlib.metadata import version

from mcp.server import MCPServer

from apple_calendar_mcp.eventkit_service import EventKitService

mcp = MCPServer("apple-calendar", version=version("apple-calendar-mcp"))

_EVENT_STATUS = {0: "none", 1: "confirmed", 2: "tentative", 3: "canceled"}
_AVAILABILITY = {
    -1: "not_supported",
    0: "busy",
    1: "free",
    2: "tentative",
    3: "unavailable",
}
_PARTICIPANT_STATUS = {
    0: "unknown",
    1: "pending",
    2: "accepted",
    3: "declined",
    4: "tentative",
    5: "delegated",
    6: "completed",
    7: "in_process",
}
_PARTICIPANT_ROLE = {
    0: "unknown",
    1: "required",
    2: "optional",
    3: "chair",
    4: "non_participant",
}
_PARTICIPANT_TYPE = {
    0: "unknown",
    1: "person",
    2: "room",
    3: "resource",
    4: "group",
}
_CALENDAR_TYPE = {
    0: "local",
    1: "caldav",
    2: "exchange",
    3: "subscription",
    4: "birthday",
}
_SOURCE_TYPE = {
    0: "local",
    1: "exchange",
    2: "caldav",
    3: "mobileme",
    4: "subscribed",
    5: "birthdays",
}
_ALARM_PROXIMITY = {0: "none", 1: "enter", 2: "leave"}
_FREQUENCY = {0: "daily", 1: "weekly", 2: "monthly", 3: "yearly"}
_WEEKDAY = {
    1: "sunday",
    2: "monday",
    3: "tuesday",
    4: "wednesday",
    5: "thursday",
    6: "friday",
    7: "saturday",
}

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


def _enum_name(mapping: dict[int, str], value):
    """Map an EventKit enum value to its name, passing unknown values through."""
    if value is None:
        return None
    return mapping.get(value, value)


def _format_participant(participant) -> dict:
    url = participant.URL()
    email = str(url) if url else None
    if email and email.startswith("mailto:"):
        email = email[len("mailto:") :]
    return {
        "name": participant.name(),
        "email": email,
        "status": _enum_name(
            _PARTICIPANT_STATUS, participant.participantStatus()
        ),
        "role": _enum_name(_PARTICIPANT_ROLE, participant.participantRole()),
        "type": _enum_name(_PARTICIPANT_TYPE, participant.participantType()),
        "is_current_user": bool(participant.isCurrentUser()),
    }


def _format_alarm(alarm) -> dict:
    absolute = alarm.absoluteDate()
    if absolute is not None:
        result = {"absolute_date": _format_nsdate(absolute)}
    else:
        offset = alarm.relativeOffset()
        result = {
            "relative_offset_minutes": (
                int(offset / 60) if offset is not None else None
            )
        }
    proximity = _enum_name(_ALARM_PROXIMITY, alarm.proximity())
    if proximity != "none":
        result["proximity"] = proximity
    return result


def _format_day_of_week(day):
    name = _enum_name(_WEEKDAY, day.dayOfTheWeek())
    week = day.weekNumber()
    if week:
        return {"day": name, "week": int(week)}
    return name


def _format_recurrence_rule(rule) -> dict:
    result = {
        "frequency": _enum_name(_FREQUENCY, rule.frequency()),
        "interval": rule.interval(),
    }
    days = rule.daysOfTheWeek()
    if days:
        result["days_of_week"] = [_format_day_of_week(day) for day in days]
    for key, values in (
        ("days_of_month", rule.daysOfTheMonth()),
        ("months_of_year", rule.monthsOfTheYear()),
        ("week_positions", rule.setPositions()),
    ):
        if values:
            result[key] = [int(value) for value in values]
    end = rule.recurrenceEnd()
    if end is not None:
        end_date = end.endDate()
        if end_date is not None:
            result["end"] = {"date": _format_nsdate(end_date)}
        elif end.occurrenceCount():
            result["end"] = {"occurrence_count": int(end.occurrenceCount())}
    return result


def _format_color(color) -> str | None:
    if color is None:
        return None
    try:
        red = color.redComponent()
        green = color.greenComponent()
        blue = color.blueComponent()
    except Exception:
        # NSColor raises for pattern and catalog colors rather than converting.
        return None
    return "#{:02x}{:02x}{:02x}".format(
        round(red * 255), round(green * 255), round(blue * 255)
    )


def _format_calendar(calendar) -> dict:
    source = calendar.source()
    return {
        "id": calendar.calendarIdentifier(),
        "name": calendar.title(),
        "type": _enum_name(_CALENDAR_TYPE, calendar.type()),
        "source": source.title() if source else None,
        "source_type": (
            _enum_name(_SOURCE_TYPE, source.sourceType()) if source else None
        ),
        "writable": bool(calendar.allowsContentModifications()),
        "immutable": bool(calendar.isImmutable()),
        "subscribed": bool(calendar.isSubscribed()),
        "color": _format_color(calendar.color()),
    }


def _format_geo(location) -> dict | None:
    if location is None:
        return None
    geo = location.geoLocation()
    if geo is None:
        return None
    coordinate = geo.coordinate()
    result = {
        "title": location.title(),
        "latitude": coordinate.latitude,
        "longitude": coordinate.longitude,
    }
    radius = location.radius()
    if radius:
        result["radius"] = radius
    return result


def _format_event(event) -> dict:
    calendar = event.calendar()
    identifier = event.calendarItemIdentifier()
    occurrence = event.occurrenceDate()
    time_zone = event.timeZone()
    url = event.URL()

    if occurrence is not None and event.hasRecurrenceRules():
        event_id = f"{identifier}/{_format_nsdate(occurrence)}"
    else:
        event_id = identifier

    result = {
        "id": event_id,
        "series_id": identifier,
        "title": event.title(),
        "start_date": _format_nsdate(event.startDate()),
        "end_date": _format_nsdate(event.endDate()),
        "is_all_day": bool(event.isAllDay()),
        "location": event.location(),
        "url": str(url) if url else None,
        "notes": event.notes(),
        "calendar": calendar.title() if calendar else None,
        "calendar_id": calendar.calendarIdentifier() if calendar else None,
        "has_recurrence": bool(event.hasRecurrenceRules()),
        "status": _enum_name(_EVENT_STATUS, event.status()),
        "availability": _enum_name(_AVAILABILITY, event.availability()),
        "time_zone": time_zone.name() if time_zone else None,
        "is_detached": bool(event.isDetached()),
        "occurrence_date": _format_nsdate(occurrence),
        "created_at": _format_nsdate(event.creationDate()),
        "last_modified": _format_nsdate(event.lastModifiedDate()),
        "external_id": event.calendarItemExternalIdentifier(),
    }

    organizer = event.organizer()
    if organizer is not None:
        result["organizer"] = _format_participant(organizer)

    attendees = event.attendees()
    if attendees:
        result["attendees"] = [
            _format_participant(attendee) for attendee in attendees
        ]

    alarms = event.alarms()
    if alarms:
        result["alarms"] = [_format_alarm(alarm) for alarm in alarms]

    rules = event.recurrenceRules()
    if rules:
        result["recurrence_rules"] = [
            _format_recurrence_rule(rule) for rule in rules
        ]

    geo = _format_geo(event.structuredLocation())
    if geo is not None:
        result["geo"] = geo

    return result


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
            **_format_calendar(cal),
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
    recurrence: str | dict | None = None,
    availability: str | None = None,
    time_zone: str | None = None,
    alarm_minutes_before: list[int] | None = None,
) -> dict:
    """Creates a calendar event. start_date in ISO 8601 format. If end_date is omitted, defaults to start + 1 hour (or +1 day if all-day). Optional: calendar_name or calendar_id (preferred, avoids ambiguity), is_all_day, location, url, notes, availability (busy/free/tentative/unavailable), time_zone (IANA name, e.g. Europe/Berlin), alarm_minutes_before (e.g. [10, 60] for reminders 10 and 60 minutes ahead). recurrence is either a frequency string (daily/weekly/monthly/yearly) or an object {"frequency": required, "interval": every N periods, "days_of_week": ["monday", ...], "end_date": ISO date, "count": number of occurrences} — end_date and count are mutually exclusive."""
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
        availability=availability,
        time_zone=time_zone,
        alarm_minutes_before=alarm_minutes_before,
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
    availability: str | None = None,
    time_zone: str | None = None,
    alarm_minutes_before: list[int] | None = None,
    recurrence: str | dict | None = None,
    span: str = "this",
) -> dict:
    """Updates an existing event. Only provided fields are changed. Dates in ISO 8601 format. availability is busy/free/tentative/unavailable, time_zone an IANA name, alarm_minutes_before a list like [10, 60] ([] clears alarms). recurrence takes a frequency string or the object described by create_event ("" clears it). For recurring events, span='this' (default) changes only this occurrence, span='future' changes this and all future ones."""
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
        availability=availability,
        time_zone=time_zone,
        alarm_minutes_before=alarm_minutes_before,
        recurrence=recurrence,
        span=span,
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
        print(f"apple-calendar-mcp {version('apple-calendar-mcp')}")
        sys.exit(0)
    mcp.run()


if __name__ == "__main__":
    main()

from __future__ import annotations

from datetime import datetime

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
    latitude, longitude = geo.coordinate()
    result = {
        "title": location.title(),
        "latitude": latitude,
        "longitude": longitude,
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

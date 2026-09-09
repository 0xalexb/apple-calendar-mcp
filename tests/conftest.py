from __future__ import annotations

from unittest.mock import MagicMock


class MockNSDate:
    """Simulates an NSDate object."""

    def __init__(self, timestamp: float):
        self._timestamp = timestamp

    def timeIntervalSince1970(self):
        return self._timestamp


class MockNSURL:
    """Simulates an NSURL object."""

    def __init__(self, url: str):
        self._url = url

    def __str__(self):
        return self._url

    def __bool__(self):
        return True


class MockTimeZone:
    """Simulates an NSTimeZone object."""

    def __init__(self, name: str):
        self._name = name

    def name(self):
        return self._name


class MockSource:
    """Simulates an EKSource object."""

    def __init__(self, title: str = "iCloud", source_type: int = 2):
        self._title = title
        self._source_type = source_type

    def title(self):
        return self._title

    def sourceType(self):
        return self._source_type


class MockCalendar:
    """Simulates an EKCalendar object."""

    _counter = 0

    def __init__(
        self,
        name: str,
        identifier: str | None = None,
        *,
        source: MockSource | None = None,
        calendar_type: int = 1,
        writable: bool = True,
        immutable: bool = False,
        subscribed: bool = False,
        color: str | None = None,
    ):
        self._title = name
        if identifier is not None:
            self._identifier = identifier
        else:
            MockCalendar._counter += 1
            self._identifier = f"cal-{MockCalendar._counter}"
        self._source = MockSource() if source is None else source
        self._type = calendar_type
        self._writable = writable
        self._immutable = immutable
        self._subscribed = subscribed
        self._color = color

    def title(self):
        return self._title

    def setTitle_(self, title):
        self._title = title

    def calendarIdentifier(self):
        return self._identifier

    def source(self):
        return self._source

    def setSource_(self, source):
        self._source = source

    def type(self):
        return self._type

    def allowsContentModifications(self):
        return self._writable

    def isImmutable(self):
        return self._immutable

    def isSubscribed(self):
        return self._subscribed

    def color(self):
        return self._color


class MockParticipant:
    """Simulates an EKParticipant object."""

    def __init__(
        self,
        name: str = "",
        email: str | None = None,
        status: int = 0,
        role: int = 0,
        participant_type: int = 1,
        is_current_user: bool = False,
    ):
        self._name = name
        self._url = MockNSURL(f"mailto:{email}") if email else None
        self._status = status
        self._role = role
        self._type = participant_type
        self._is_current_user = is_current_user

    def name(self):
        return self._name

    def URL(self):
        return self._url

    def participantStatus(self):
        return self._status

    def participantRole(self):
        return self._role

    def participantType(self):
        return self._type

    def isCurrentUser(self):
        return self._is_current_user


class MockAlarm:
    """Simulates an EKAlarm object."""

    def __init__(
        self,
        relative_offset: float | None = None,
        absolute_date: MockNSDate | None = None,
        proximity: int = 0,
    ):
        self._relative_offset = relative_offset
        self._absolute_date = absolute_date
        self._proximity = proximity

    def relativeOffset(self):
        return self._relative_offset

    def absoluteDate(self):
        return self._absolute_date

    def proximity(self):
        return self._proximity


class MockDayOfWeek:
    """Simulates an EKRecurrenceDayOfWeek object."""

    def __init__(self, day: int, week_number: int = 0):
        self._day = day
        self._week_number = week_number

    def dayOfTheWeek(self):
        return self._day

    def weekNumber(self):
        return self._week_number


class MockRecurrenceEnd:
    """Simulates an EKRecurrenceEnd object."""

    def __init__(
        self,
        end_date: MockNSDate | None = None,
        occurrence_count: int = 0,
    ):
        self._end_date = end_date
        self._occurrence_count = occurrence_count

    def endDate(self):
        return self._end_date

    def occurrenceCount(self):
        return self._occurrence_count


class MockRecurrenceRule:
    """Simulates an EKRecurrenceRule object."""

    def __init__(
        self,
        frequency: int = 1,
        interval: int = 1,
        days_of_week: list[MockDayOfWeek] | None = None,
        days_of_month: list[int] | None = None,
        months_of_year: list[int] | None = None,
        set_positions: list[int] | None = None,
        recurrence_end: MockRecurrenceEnd | None = None,
    ):
        self._frequency = frequency
        self._interval = interval
        self._days_of_week = days_of_week
        self._days_of_month = days_of_month
        self._months_of_year = months_of_year
        self._set_positions = set_positions
        self._recurrence_end = recurrence_end

    def frequency(self):
        return self._frequency

    def interval(self):
        return self._interval

    def daysOfTheWeek(self):
        return self._days_of_week

    def daysOfTheMonth(self):
        return self._days_of_month

    def monthsOfTheYear(self):
        return self._months_of_year

    def setPositions(self):
        return self._set_positions

    def recurrenceEnd(self):
        return self._recurrence_end


class MockCoordinate:
    """Simulates a CLLocationCoordinate2D struct."""

    def __init__(self, latitude: float, longitude: float):
        self.latitude = latitude
        self.longitude = longitude


class MockGeoLocation:
    """Simulates a CLLocation object."""

    def __init__(self, latitude: float, longitude: float):
        self._coordinate = MockCoordinate(latitude, longitude)

    def coordinate(self):
        return self._coordinate


class MockStructuredLocation:
    """Simulates an EKStructuredLocation object."""

    def __init__(
        self,
        title: str | None = None,
        geo_location: MockGeoLocation | None = None,
        radius: float = 0.0,
    ):
        self._title = title
        self._geo_location = geo_location
        self._radius = radius

    def title(self):
        return self._title

    def geoLocation(self):
        return self._geo_location

    def radius(self):
        return self._radius


class MockEvent:
    """Simulates an EKEvent object, with both accessors and setters."""

    def __init__(
        self,
        title: str = "",
        identifier: str = "evt-1",
        calendar: MockCalendar | None = None,
        start_date: MockNSDate | None = None,
        end_date: MockNSDate | None = None,
        is_all_day: bool = False,
        location: str | None = None,
        url: MockNSURL | None = None,
        notes: str | None = None,
        has_recurrence: bool = False,
        status: int = 0,
        availability: int = 0,
        time_zone: MockTimeZone | None = None,
        is_detached: bool = False,
        occurrence_date: MockNSDate | None = None,
        creation_date: MockNSDate | None = None,
        last_modified: MockNSDate | None = None,
        external_id: str | None = None,
        organizer: MockParticipant | None = None,
        attendees: list[MockParticipant] | None = None,
        alarms: list[MockAlarm] | None = None,
        recurrence_rules: list[MockRecurrenceRule] | None = None,
        structured_location: MockStructuredLocation | None = None,
    ):
        self._title = title
        self._identifier = identifier
        self._calendar = calendar
        self._start_date = start_date
        self._end_date = end_date
        self._is_all_day = is_all_day
        self._location = location
        self._url = url
        self._notes = notes
        self._has_recurrence = has_recurrence
        self._status = status
        self._availability = availability
        self._time_zone = time_zone
        self._is_detached = is_detached
        self._occurrence_date = occurrence_date
        self._creation_date = creation_date
        self._last_modified = last_modified
        self._external_id = external_id
        self._organizer = organizer
        self._attendees = attendees
        self._alarms = alarms
        self._recurrence_rules = list(recurrence_rules) if recurrence_rules else []
        self._structured_location = structured_location

    def title(self):
        return self._title

    def setTitle_(self, title):
        self._title = title

    def calendarItemIdentifier(self):
        return self._identifier

    def calendar(self):
        return self._calendar

    def setCalendar_(self, calendar):
        self._calendar = calendar

    def startDate(self):
        return self._start_date

    def setStartDate_(self, date):
        self._start_date = date

    def endDate(self):
        return self._end_date

    def setEndDate_(self, date):
        self._end_date = date

    def isAllDay(self):
        return self._is_all_day

    def setAllDay_(self, all_day):
        self._is_all_day = all_day

    def location(self):
        return self._location

    def setLocation_(self, location):
        self._location = location

    def URL(self):
        return self._url

    def setURL_(self, url):
        self._url = url

    def notes(self):
        return self._notes

    def setNotes_(self, notes):
        self._notes = notes

    def hasRecurrenceRules(self):
        return self._has_recurrence or bool(self._recurrence_rules)

    def recurrenceRules(self):
        return self._recurrence_rules

    def addRecurrenceRule_(self, rule):
        self._recurrence_rules.append(rule)

    def setRecurrenceRules_(self, rules):
        self._recurrence_rules = list(rules) if rules else []

    def status(self):
        return self._status

    def availability(self):
        return self._availability

    def setAvailability_(self, availability):
        self._availability = availability

    def timeZone(self):
        return self._time_zone

    def setTimeZone_(self, time_zone):
        self._time_zone = time_zone

    def isDetached(self):
        return self._is_detached

    def occurrenceDate(self):
        return self._occurrence_date

    def creationDate(self):
        return self._creation_date

    def lastModifiedDate(self):
        return self._last_modified

    def calendarItemExternalIdentifier(self):
        return self._external_id

    def organizer(self):
        return self._organizer

    def attendees(self):
        return self._attendees

    def alarms(self):
        return self._alarms

    def setAlarms_(self, alarms):
        self._alarms = list(alarms) if alarms else None

    def structuredLocation(self):
        return self._structured_location


def make_ek_module():
    """Create a mock EventKit module with the constants the service reads."""
    ek = MagicMock()
    ek.EKEntityTypeEvent = 0
    return ek


def make_store(calendars=None, events=None):
    """Create a mock EKEventStore with successful save/remove defaults."""
    store = MagicMock()
    store.calendarsForEntityType_.return_value = calendars or []
    store.defaultCalendarForNewEvents.return_value = MockCalendar(
        "Default", "default-cal"
    )
    store.eventsMatchingPredicate_.return_value = events
    store.saveCalendar_commit_error_.return_value = (True, None)
    store.saveEvent_span_commit_error_.return_value = (True, None)
    store.removeEvent_span_commit_error_.return_value = (True, None)
    return store

from __future__ import annotations

from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

from apple_calendar_mcp.server import (
    _format_alarm,
    _format_calendar,
    _format_event,
    _format_nsdate,
    _format_participant,
    _format_recurrence_rule,
    get_all_events,
    get_events,
    list_calendars,
)
from tests.conftest import (
    MockAlarm,
    MockCalendar,
    MockDayOfWeek,
    MockEvent,
    MockGeoLocation,
    MockNSDate,
    MockNSURL,
    MockParticipant,
    MockRecurrenceEnd,
    MockRecurrenceRule,
    MockSource,
    MockStructuredLocation,
    MockTimeZone,
)


@pytest.fixture()
def mock_service():
    service = MagicMock()
    with patch(
        "apple_calendar_mcp.server._get_service", return_value=service
    ):
        yield service


# ---------------------------------------------------------------------------
# Tests: _format_nsdate
# ---------------------------------------------------------------------------


class TestFormatNsdate:
    def test_returns_iso_string(self):
        nsdate = MockNSDate(1742036400.0)
        result = _format_nsdate(nsdate)
        expected = datetime.fromtimestamp(1742036400.0).isoformat()
        assert result == expected

    def test_returns_none_for_none(self):
        assert _format_nsdate(None) is None

    def test_midnight_timestamp(self):
        nsdate = MockNSDate(0.0)
        result = _format_nsdate(nsdate)
        expected = datetime.fromtimestamp(0.0).isoformat()
        assert result == expected


# ---------------------------------------------------------------------------
# Tests: _format_event
# ---------------------------------------------------------------------------


class TestFormatEvent:
    def test_full_event(self):
        cal = MockCalendar("Work", "cal-work")
        start = MockNSDate(1742036400.0)
        end = MockNSDate(1742040000.0)
        url = MockNSURL("https://example.com")
        event = MockEvent(
            title="Meeting",
            identifier="evt-1",
            calendar=cal,
            start_date=start,
            end_date=end,
            is_all_day=False,
            location="Office",
            url=url,
            notes="Bring slides",
            has_recurrence=True,
        )

        result = _format_event(event)

        assert result["id"] == "evt-1"
        assert result["title"] == "Meeting"
        assert result["start_date"] == datetime.fromtimestamp(1742036400.0).isoformat()
        assert result["end_date"] == datetime.fromtimestamp(1742040000.0).isoformat()
        assert result["is_all_day"] is False
        assert result["location"] == "Office"
        assert result["url"] == "https://example.com"
        assert result["notes"] == "Bring slides"
        assert result["calendar"] == "Work"
        assert result["calendar_id"] == "cal-work"
        assert result["has_recurrence"] is True

    def test_minimal_event(self):
        event = MockEvent(title="Quick", identifier="evt-2")

        result = _format_event(event)

        assert result["id"] == "evt-2"
        assert result["title"] == "Quick"
        assert result["start_date"] is None
        assert result["end_date"] is None
        assert result["is_all_day"] is False
        assert result["location"] is None
        assert result["url"] is None
        assert result["notes"] is None
        assert result["calendar"] is None
        assert result["calendar_id"] is None
        assert result["has_recurrence"] is False

    def test_event_without_url(self):
        cal = MockCalendar("Personal")
        event = MockEvent(
            title="Lunch",
            identifier="evt-3",
            calendar=cal,
            url=None,
        )

        result = _format_event(event)
        assert result["url"] is None

    def test_all_day_event(self):
        cal = MockCalendar("Personal")
        start = MockNSDate(1742036400.0)
        end = MockNSDate(1742122800.0)
        event = MockEvent(
            title="Holiday",
            calendar=cal,
            start_date=start,
            end_date=end,
            is_all_day=True,
        )

        result = _format_event(event)
        assert result["is_all_day"] is True


# ---------------------------------------------------------------------------
# Tests: list_calendars
# ---------------------------------------------------------------------------


class TestListCalendars:
    def test_returns_calendars_with_counts(self, mock_service):
        cal1 = MockCalendar("Work", "cal-w")
        cal2 = MockCalendar("Personal", "cal-p")
        mock_service.get_all_calendars.return_value = [cal1, cal2]

        evt1 = MockEvent(title="Meeting", calendar=cal1)
        evt2 = MockEvent(title="Lunch", calendar=cal1)
        evt3 = MockEvent(title="Dinner", calendar=cal2)
        mock_service.get_all_events.return_value = [evt1, evt2, evt3]

        result = list_calendars()

        assert len(result) == 2
        assert result[0] == {
            "id": "cal-w",
            "name": "Work",
            "type": "caldav",
            "source": "iCloud",
            "source_type": "caldav",
            "writable": True,
            "immutable": False,
            "subscribed": False,
            "color": None,
            "upcoming_event_count": 2,
        }
        assert result[1] == {
            "id": "cal-p",
            "name": "Personal",
            "type": "caldav",
            "source": "iCloud",
            "source_type": "caldav",
            "writable": True,
            "immutable": False,
            "subscribed": False,
            "color": None,
            "upcoming_event_count": 1,
        }

    def test_empty_calendars(self, mock_service):
        mock_service.get_all_calendars.return_value = []
        mock_service.get_all_events.return_value = []

        result = list_calendars()
        assert result == []

    def test_calendar_with_no_events(self, mock_service):
        cal = MockCalendar("Empty", "cal-e")
        mock_service.get_all_calendars.return_value = [cal]
        mock_service.get_all_events.return_value = []

        result = list_calendars()

        assert len(result) == 1
        assert result[0] == {
            "id": "cal-e",
            "name": "Empty",
            "type": "caldav",
            "source": "iCloud",
            "source_type": "caldav",
            "writable": True,
            "immutable": False,
            "subscribed": False,
            "color": None,
            "upcoming_event_count": 0,
        }


# ---------------------------------------------------------------------------
# Tests: get_events
# ---------------------------------------------------------------------------


class TestGetEvents:
    def test_returns_formatted_events(self, mock_service):
        cal = MockCalendar("Work")
        start = MockNSDate(1742036400.0)
        end = MockNSDate(1742040000.0)
        evt = MockEvent(
            title="Meeting",
            identifier="evt-1",
            calendar=cal,
            start_date=start,
            end_date=end,
        )
        mock_service.get_events.return_value = [evt]

        result = get_events(start_date="2026-03-15", calendar_name="Work")

        assert len(result) == 1
        assert result[0]["title"] == "Meeting"
        mock_service.get_events.assert_called_once_with(
            "Work",
            datetime(2026, 3, 15),
            datetime(2026, 3, 16),
            calendar_id=None,
        )

    def test_with_explicit_end_date(self, mock_service):
        mock_service.get_events.return_value = []

        get_events(
            start_date="2026-03-15",
            end_date="2026-03-20",
            calendar_name="Work",
        )

        mock_service.get_events.assert_called_once_with(
            "Work",
            datetime(2026, 3, 15),
            datetime(2026, 3, 20),
            calendar_id=None,
        )

    def test_with_calendar_id(self, mock_service):
        mock_service.get_events.return_value = []

        get_events(start_date="2026-03-15", calendar_name="Work", calendar_id="cal-w1")

        mock_service.get_events.assert_called_once_with(
            "Work",
            datetime(2026, 3, 15),
            datetime(2026, 3, 16),
            calendar_id="cal-w1",
        )

    def test_with_calendar_id_only(self, mock_service):
        mock_service.get_events.return_value = []

        get_events(start_date="2026-03-15", calendar_id="cal-w1")

        mock_service.get_events.assert_called_once_with(
            None,
            datetime(2026, 3, 15),
            datetime(2026, 3, 16),
            calendar_id="cal-w1",
        )

    def test_with_calendar_id_overrides_name(self, mock_service):
        mock_service.get_events.return_value = []

        get_events(start_date="2026-03-15", calendar_name="Work", calendar_id="cal-w1")

        mock_service.get_events.assert_called_once_with(
            "Work",
            datetime(2026, 3, 15),
            datetime(2026, 3, 16),
            calendar_id="cal-w1",
        )

    def test_empty_result(self, mock_service):
        mock_service.get_events.return_value = []

        result = get_events(start_date="2026-03-15", calendar_name="Work")
        assert result == []

    def test_service_error_propagates(self, mock_service):
        mock_service.get_events.side_effect = ValueError(
            "Calendar 'Missing' not found"
        )

        with pytest.raises(ValueError, match="not found"):
            get_events(start_date="2026-03-15", calendar_name="Missing")


# ---------------------------------------------------------------------------
# Tests: get_all_events
# ---------------------------------------------------------------------------


class TestGetAllEvents:
    def test_returns_grouped_events(self, mock_service):
        cal1 = MockCalendar("Work", "cal-w")
        cal2 = MockCalendar("Personal", "cal-p")
        start = MockNSDate(1742036400.0)
        end = MockNSDate(1742040000.0)
        evt1 = MockEvent(
            title="Meeting", calendar=cal1, start_date=start, end_date=end
        )
        evt2 = MockEvent(
            title="Dinner", calendar=cal2, start_date=start, end_date=end
        )
        mock_service.get_all_events.return_value = [evt1, evt2]

        result = get_all_events("2026-03-15")

        assert "Work" in result
        assert "Personal" in result
        assert len(result["Work"]) == 1
        assert len(result["Personal"]) == 1
        assert result["Work"][0]["title"] == "Meeting"
        assert result["Personal"][0]["title"] == "Dinner"

    def test_with_explicit_end_date(self, mock_service):
        mock_service.get_all_events.return_value = []

        get_all_events("2026-03-15", "2026-03-20")

        mock_service.get_all_events.assert_called_once_with(
            datetime(2026, 3, 15),
            datetime(2026, 3, 20),
        )

    def test_default_end_date(self, mock_service):
        mock_service.get_all_events.return_value = []

        get_all_events("2026-03-15")

        mock_service.get_all_events.assert_called_once_with(
            datetime(2026, 3, 15),
            datetime(2026, 3, 16),
        )

    def test_empty_result(self, mock_service):
        mock_service.get_all_events.return_value = []

        result = get_all_events("2026-03-15")
        assert result == {}

    def test_events_without_calendar(self, mock_service):
        start = MockNSDate(1742036400.0)
        end = MockNSDate(1742040000.0)
        evt = MockEvent(
            title="Orphan", calendar=None, start_date=start, end_date=end
        )
        mock_service.get_all_events.return_value = [evt]

        result = get_all_events("2026-03-15")

        assert "Unknown" in result
        assert result["Unknown"][0]["title"] == "Orphan"

    def test_duplicate_name_calendars_grouped_by_name(self, mock_service):
        cal1 = MockCalendar("Work", "cal-w1")
        cal2 = MockCalendar("Work", "cal-w2")
        start = MockNSDate(1742036400.0)
        end = MockNSDate(1742040000.0)
        evt1 = MockEvent(
            title="Meeting A", calendar=cal1, start_date=start, end_date=end
        )
        evt2 = MockEvent(
            title="Meeting B", calendar=cal2, start_date=start, end_date=end
        )
        mock_service.get_all_events.return_value = [evt1, evt2]

        result = get_all_events("2026-03-15")

        assert "Work" in result
        assert len(result["Work"]) == 2
        titles = {e["title"] for e in result["Work"]}
        assert titles == {"Meeting A", "Meeting B"}
        # Individual events retain calendar_id for disambiguation
        ids = {e["calendar_id"] for e in result["Work"]}
        assert ids == {"cal-w1", "cal-w2"}


# ---------------------------------------------------------------------------
# Tests: field formatters
# ---------------------------------------------------------------------------


class TestFormatParticipant:
    @pytest.mark.parametrize(
        "value,expected",
        [
            (0, "unknown"),
            (1, "pending"),
            (2, "accepted"),
            (3, "declined"),
            (4, "tentative"),
            (5, "delegated"),
            (6, "completed"),
            (7, "in_process"),
        ],
    )
    def test_status_names(self, value, expected):
        participant = MockParticipant(status=value)
        assert _format_participant(participant)["status"] == expected

    @pytest.mark.parametrize(
        "value,expected",
        [
            (0, "unknown"),
            (1, "required"),
            (2, "optional"),
            (3, "chair"),
            (4, "non_participant"),
        ],
    )
    def test_role_names(self, value, expected):
        participant = MockParticipant(role=value)
        assert _format_participant(participant)["role"] == expected

    @pytest.mark.parametrize(
        "value,expected",
        [
            (0, "unknown"),
            (1, "person"),
            (2, "room"),
            (3, "resource"),
            (4, "group"),
        ],
    )
    def test_type_names(self, value, expected):
        participant = MockParticipant(participant_type=value)
        assert _format_participant(participant)["type"] == expected

    def test_strips_mailto_prefix(self):
        participant = MockParticipant(name="Ada", email="ada@example.com")
        result = _format_participant(participant)
        assert result["name"] == "Ada"
        assert result["email"] == "ada@example.com"

    def test_email_none_without_url(self):
        assert _format_participant(MockParticipant())["email"] is None

    def test_unknown_enum_falls_back_to_raw_value(self):
        participant = MockParticipant(status=99)
        assert _format_participant(participant)["status"] == 99


class TestFormatAlarm:
    def test_relative_offset_converted_to_minutes(self):
        result = _format_alarm(MockAlarm(relative_offset=-600))
        assert result == {"relative_offset_minutes": -10}

    def test_absolute_date(self):
        alarm = MockAlarm(absolute_date=MockNSDate(1742036400.0))
        result = _format_alarm(alarm)
        assert result == {
            "absolute_date": datetime.fromtimestamp(1742036400.0).isoformat()
        }

    def test_proximity_omitted_when_none(self):
        assert "proximity" not in _format_alarm(MockAlarm(relative_offset=0))

    @pytest.mark.parametrize("value,expected", [(1, "enter"), (2, "leave")])
    def test_proximity_included_when_set(self, value, expected):
        alarm = MockAlarm(relative_offset=-60, proximity=value)
        assert _format_alarm(alarm)["proximity"] == expected


class TestFormatRecurrenceRule:
    @pytest.mark.parametrize(
        "value,expected",
        [(0, "daily"), (1, "weekly"), (2, "monthly"), (3, "yearly")],
    )
    def test_frequency_names(self, value, expected):
        rule = MockRecurrenceRule(frequency=value)
        assert _format_recurrence_rule(rule)["frequency"] == expected

    def test_minimal_rule_has_only_frequency_and_interval(self):
        rule = MockRecurrenceRule(frequency=1, interval=2)
        assert _format_recurrence_rule(rule) == {
            "frequency": "weekly",
            "interval": 2,
        }

    def test_days_of_week_as_names(self):
        rule = MockRecurrenceRule(
            days_of_week=[MockDayOfWeek(2), MockDayOfWeek(5)]
        )
        result = _format_recurrence_rule(rule)
        assert result["days_of_week"] == ["monday", "thursday"]

    def test_day_of_week_with_week_number(self):
        rule = MockRecurrenceRule(days_of_week=[MockDayOfWeek(3, 2)])
        result = _format_recurrence_rule(rule)
        assert result["days_of_week"] == [{"day": "tuesday", "week": 2}]

    def test_optional_axes_included_when_set(self):
        rule = MockRecurrenceRule(
            days_of_month=[1, 15],
            months_of_year=[3],
            set_positions=[-1],
        )
        result = _format_recurrence_rule(rule)
        assert result["days_of_month"] == [1, 15]
        assert result["months_of_year"] == [3]
        assert result["week_positions"] == [-1]

    def test_end_date(self):
        end = MockRecurrenceEnd(end_date=MockNSDate(1742036400.0))
        rule = MockRecurrenceRule(recurrence_end=end)
        result = _format_recurrence_rule(rule)
        assert result["end"] == {
            "date": datetime.fromtimestamp(1742036400.0).isoformat()
        }

    def test_end_occurrence_count(self):
        rule = MockRecurrenceRule(
            recurrence_end=MockRecurrenceEnd(occurrence_count=10)
        )
        assert _format_recurrence_rule(rule)["end"] == {"occurrence_count": 10}

    def test_nil_end_omits_key(self):
        assert "end" not in _format_recurrence_rule(MockRecurrenceRule())


class TestFormatCalendar:
    @pytest.mark.parametrize(
        "value,expected",
        [
            (0, "local"),
            (1, "caldav"),
            (2, "exchange"),
            (3, "subscription"),
            (4, "birthday"),
        ],
    )
    def test_type_names(self, value, expected):
        cal = MockCalendar("Work", "cal-1", calendar_type=value)
        assert _format_calendar(cal)["type"] == expected

    @pytest.mark.parametrize(
        "value,expected",
        [
            (0, "local"),
            (1, "exchange"),
            (2, "caldav"),
            (3, "mobileme"),
            (4, "subscribed"),
            (5, "birthdays"),
        ],
    )
    def test_source_type_names(self, value, expected):
        cal = MockCalendar(
            "Work", "cal-1", source=MockSource("Acct", value)
        )
        assert _format_calendar(cal)["source_type"] == expected

    def test_read_only_calendar(self):
        cal = MockCalendar("Holidays", "cal-h", writable=False, immutable=True)
        result = _format_calendar(cal)
        assert result["writable"] is False
        assert result["immutable"] is True

    def test_subscribed_calendar(self):
        cal = MockCalendar("Feed", "cal-f", subscribed=True)
        assert _format_calendar(cal)["subscribed"] is True

    def test_nil_source(self):
        cal = MockCalendar("Orphan", "cal-o", source=False)
        result = _format_calendar(cal)
        assert result["source"] is None
        assert result["source_type"] is None


class TestFormatEventNewFields:
    def test_full_event_has_every_key(self):
        event = MockEvent(
            title="Standup",
            identifier="evt-9",
            calendar=MockCalendar("Work", "cal-work"),
            start_date=MockNSDate(1742036400.0),
            end_date=MockNSDate(1742040000.0),
            status=3,
            availability=1,
            time_zone=MockTimeZone("Europe/Berlin"),
            is_detached=True,
            occurrence_date=MockNSDate(1742036400.0),
            creation_date=MockNSDate(1700000000.0),
            last_modified=MockNSDate(1710000000.0),
            external_id="ext-9",
            organizer=MockParticipant(name="Ada", email="ada@example.com"),
            attendees=[MockParticipant(name="Bob", email="bob@example.com")],
            alarms=[MockAlarm(relative_offset=-900)],
            recurrence_rules=[MockRecurrenceRule(frequency=1)],
            structured_location=MockStructuredLocation(
                title="HQ",
                geo_location=MockGeoLocation(52.52, 13.405),
                radius=100.0,
            ),
        )

        result = _format_event(event)

        assert result["status"] == "canceled"
        assert result["availability"] == "free"
        assert result["time_zone"] == "Europe/Berlin"
        assert result["is_detached"] is True
        assert result["external_id"] == "ext-9"
        assert result["series_id"] == "evt-9"
        assert result["created_at"] == datetime.fromtimestamp(1700000000.0).isoformat()
        assert result["last_modified"] == datetime.fromtimestamp(1710000000.0).isoformat()
        assert result["organizer"]["email"] == "ada@example.com"
        assert result["attendees"] == [
            {
                "name": "Bob",
                "email": "bob@example.com",
                "status": "unknown",
                "role": "unknown",
                "type": "person",
                "is_current_user": False,
            }
        ]
        assert result["alarms"] == [{"relative_offset_minutes": -15}]
        assert result["recurrence_rules"] == [
            {"frequency": "weekly", "interval": 1}
        ]
        assert result["geo"] == {
            "title": "HQ",
            "latitude": 52.52,
            "longitude": 13.405,
            "radius": 100.0,
        }

    def test_minimal_event_omits_optional_collections(self):
        result = _format_event(MockEvent(title="Solo", identifier="evt-10"))

        optional = {"organizer", "attendees", "alarms", "recurrence_rules", "geo"}
        assert set(result) & optional == set()
        assert result["status"] == "none"
        assert result["availability"] == "busy"
        assert result["time_zone"] is None

    def test_empty_collections_omitted(self):
        event = MockEvent(attendees=[], alarms=[], recurrence_rules=[])
        result = _format_event(event)
        assert "attendees" not in result
        assert "alarms" not in result
        assert "recurrence_rules" not in result

    def test_structured_location_without_coordinates_omits_geo(self):
        event = MockEvent(
            structured_location=MockStructuredLocation(title="Somewhere")
        )
        assert "geo" not in _format_event(event)

from __future__ import annotations

from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

from apple_calendar_mcp.server import (
    _format_event,
    _format_nsdate,
    get_all_events,
    get_events,
    list_calendars,
)


# ---------------------------------------------------------------------------
# Mock helpers
# ---------------------------------------------------------------------------


class MockCalendar:
    _counter = 0

    def __init__(self, name: str, identifier: str | None = None):
        self._title = name
        if identifier is not None:
            self._identifier = identifier
        else:
            MockCalendar._counter += 1
            self._identifier = f"cal-{MockCalendar._counter}"

    def title(self):
        return self._title

    def calendarIdentifier(self):
        return self._identifier


class MockNSDate:
    def __init__(self, timestamp: float):
        self._timestamp = timestamp

    def timeIntervalSince1970(self):
        return self._timestamp


class MockNSURL:
    def __init__(self, url: str):
        self._url = url

    def __str__(self):
        return self._url

    def __bool__(self):
        return True


class MockEvent:
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

    def title(self):
        return self._title

    def calendarItemIdentifier(self):
        return self._identifier

    def calendar(self):
        return self._calendar

    def startDate(self):
        return self._start_date

    def endDate(self):
        return self._end_date

    def isAllDay(self):
        return self._is_all_day

    def location(self):
        return self._location

    def URL(self):
        return self._url

    def notes(self):
        return self._notes

    def hasRecurrenceRules(self):
        return self._has_recurrence


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
        assert result[0] == {"id": "cal-w", "name": "Work", "upcoming_event_count": 2}
        assert result[1] == {"id": "cal-p", "name": "Personal", "upcoming_event_count": 1}

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
        assert result[0] == {"id": "cal-e", "name": "Empty", "upcoming_event_count": 0}


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

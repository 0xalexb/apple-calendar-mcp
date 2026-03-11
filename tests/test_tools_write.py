from __future__ import annotations

from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

from apple_calendar_mcp.server import (
    create_calendar,
    create_event,
    delete_event,
    move_event,
    quick_add,
    update_event,
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
# Tests: create_calendar
# ---------------------------------------------------------------------------


class TestCreateCalendar:
    def test_creates_calendar(self, mock_service):
        cal = MockCalendar("Work")
        mock_service.create_calendar.return_value = cal

        result = create_calendar("Work")

        assert result == {"name": "Work", "created": True}
        mock_service.create_calendar.assert_called_once_with("Work")

    def test_service_error_propagates(self, mock_service):
        mock_service.create_calendar.side_effect = RuntimeError(
            "Failed to create calendar"
        )

        with pytest.raises(RuntimeError, match="Failed to create"):
            create_calendar("Work")


# ---------------------------------------------------------------------------
# Tests: create_event
# ---------------------------------------------------------------------------


class TestCreateEvent:
    def test_minimal_create(self, mock_service):
        cal = MockCalendar("Default")
        start = MockNSDate(1742036400.0)
        end = MockNSDate(1742040000.0)
        evt = MockEvent(
            title="Meeting",
            identifier="evt-1",
            calendar=cal,
            start_date=start,
            end_date=end,
        )
        mock_service.create_event.return_value = evt

        result = create_event("Meeting", "2026-03-15T10:00:00")

        assert result["title"] == "Meeting"
        assert result["id"] == "evt-1"
        assert result["calendar"] == "Default"
        call_kwargs = mock_service.create_event.call_args.kwargs
        assert call_kwargs["title"] == "Meeting"
        assert call_kwargs["start_date"] == datetime(2026, 3, 15, 10, 0)
        assert call_kwargs["end_date"] == datetime(2026, 3, 15, 11, 0)
        assert call_kwargs["is_all_day"] is False

    def test_with_explicit_end_date(self, mock_service):
        cal = MockCalendar("Default")
        start = MockNSDate(1742036400.0)
        end = MockNSDate(1742047200.0)
        evt = MockEvent(
            title="Conference",
            identifier="evt-2",
            calendar=cal,
            start_date=start,
            end_date=end,
        )
        mock_service.create_event.return_value = evt

        result = create_event(
            "Conference", "2026-03-15T10:00:00", end_date="2026-03-15T13:00:00"
        )

        assert result["title"] == "Conference"
        call_kwargs = mock_service.create_event.call_args.kwargs
        assert call_kwargs["end_date"] == datetime(2026, 3, 15, 13, 0)

    def test_all_day_default_end(self, mock_service):
        cal = MockCalendar("Default")
        start = MockNSDate(1742036400.0)
        end = MockNSDate(1742122800.0)
        evt = MockEvent(
            title="Holiday",
            identifier="evt-3",
            calendar=cal,
            start_date=start,
            end_date=end,
            is_all_day=True,
        )
        mock_service.create_event.return_value = evt

        result = create_event("Holiday", "2026-03-15", is_all_day=True)

        assert result["is_all_day"] is True
        call_kwargs = mock_service.create_event.call_args.kwargs
        assert call_kwargs["end_date"] == datetime(2026, 3, 16)
        assert call_kwargs["is_all_day"] is True

    def test_with_all_options(self, mock_service):
        cal = MockCalendar("Work")
        start = MockNSDate(1742036400.0)
        end = MockNSDate(1742040000.0)
        url = MockNSURL("https://meet.example.com")
        evt = MockEvent(
            title="Meeting",
            identifier="evt-4",
            calendar=cal,
            start_date=start,
            end_date=end,
            location="Office",
            url=url,
            notes="Bring slides",
            has_recurrence=True,
        )
        mock_service.create_event.return_value = evt

        result = create_event(
            title="Meeting",
            start_date="2026-03-15T10:00:00",
            end_date="2026-03-15T11:00:00",
            calendar_name="Work",
            location="Office",
            url="https://meet.example.com",
            notes="Bring slides",
            recurrence="weekly",
        )

        assert result["title"] == "Meeting"
        assert result["location"] == "Office"
        assert result["url"] == "https://meet.example.com"
        assert result["notes"] == "Bring slides"
        assert result["has_recurrence"] is True
        call_kwargs = mock_service.create_event.call_args.kwargs
        assert call_kwargs["calendar_name"] == "Work"
        assert call_kwargs["calendar_id"] is None
        assert call_kwargs["location"] == "Office"
        assert call_kwargs["url"] == "https://meet.example.com"
        assert call_kwargs["notes"] == "Bring slides"
        assert call_kwargs["recurrence"] == "weekly"

    def test_with_calendar_id(self, mock_service):
        cal = MockCalendar("Work", "cal-w2")
        start = MockNSDate(1742036400.0)
        end = MockNSDate(1742040000.0)
        evt = MockEvent(
            title="Meeting",
            identifier="evt-10",
            calendar=cal,
            start_date=start,
            end_date=end,
        )
        mock_service.create_event.return_value = evt

        result = create_event(
            title="Meeting",
            start_date="2026-03-15T10:00:00",
            calendar_id="cal-w2",
        )

        assert result["title"] == "Meeting"
        call_kwargs = mock_service.create_event.call_args.kwargs
        assert call_kwargs["calendar_id"] == "cal-w2"
        assert call_kwargs["calendar_name"] is None

    def test_service_error_propagates(self, mock_service):
        mock_service.create_event.side_effect = ValueError(
            "Calendar 'Missing' not found"
        )

        with pytest.raises(ValueError, match="not found"):
            create_event("Task", "2026-03-15T10:00:00", calendar_name="Missing")


# ---------------------------------------------------------------------------
# Tests: update_event
# ---------------------------------------------------------------------------


class TestUpdateEvent:
    def test_update_title(self, mock_service):
        cal = MockCalendar("Work")
        start = MockNSDate(1742036400.0)
        end = MockNSDate(1742040000.0)
        evt = MockEvent(
            title="Updated",
            identifier="evt-5",
            calendar=cal,
            start_date=start,
            end_date=end,
        )
        mock_service.update_event.return_value = evt

        result = update_event("evt-5", title="Updated")

        assert result["title"] == "Updated"
        assert result["id"] == "evt-5"
        mock_service.update_event.assert_called_once_with(
            "evt-5",
            title="Updated",
            start_date=None,
            end_date=None,
            is_all_day=None,
            location=None,
            url=None,
            notes=None,
        )

    def test_update_dates(self, mock_service):
        cal = MockCalendar("Work")
        start = MockNSDate(1742472000.0)
        end = MockNSDate(1742475600.0)
        evt = MockEvent(
            title="Meeting",
            identifier="evt-5",
            calendar=cal,
            start_date=start,
            end_date=end,
        )
        mock_service.update_event.return_value = evt

        update_event(
            "evt-5",
            start_date="2026-03-20T14:00:00",
            end_date="2026-03-20T15:00:00",
        )

        call_kwargs = mock_service.update_event.call_args.kwargs
        assert call_kwargs["start_date"] == datetime(2026, 3, 20, 14, 0)
        assert call_kwargs["end_date"] == datetime(2026, 3, 20, 15, 0)

    def test_not_found_propagates(self, mock_service):
        mock_service.update_event.side_effect = ValueError(
            "Event 'bad-id' not found"
        )

        with pytest.raises(ValueError, match="not found"):
            update_event("bad-id", title="New")


# ---------------------------------------------------------------------------
# Tests: delete_event
# ---------------------------------------------------------------------------


class TestDeleteEvent:
    def test_deletes_event(self, mock_service):
        mock_service.delete_event.return_value = None

        result = delete_event("evt-6")

        assert result == {"id": "evt-6", "deleted": True}
        mock_service.delete_event.assert_called_once_with(
            "evt-6", span="this"
        )

    def test_delete_future_span(self, mock_service):
        mock_service.delete_event.return_value = None

        result = delete_event("evt-6", span="future")

        assert result == {"id": "evt-6", "deleted": True}
        mock_service.delete_event.assert_called_once_with(
            "evt-6", span="future"
        )

    def test_not_found_propagates(self, mock_service):
        mock_service.delete_event.side_effect = ValueError(
            "Event 'bad-id' not found"
        )

        with pytest.raises(ValueError, match="not found"):
            delete_event("bad-id")


# ---------------------------------------------------------------------------
# Tests: move_event
# ---------------------------------------------------------------------------


class TestMoveEvent:
    def test_moves_event(self, mock_service):
        cal = MockCalendar("Personal")
        start = MockNSDate(1742036400.0)
        end = MockNSDate(1742040000.0)
        evt = MockEvent(
            title="Moved event",
            identifier="evt-7",
            calendar=cal,
            start_date=start,
            end_date=end,
        )
        mock_service.move_event.return_value = evt

        result = move_event("evt-7", target_calendar_name="Personal")

        assert result["id"] == "evt-7"
        assert result["title"] == "Moved event"
        assert result["calendar"] == "Personal"
        mock_service.move_event.assert_called_once_with(
            "evt-7", "Personal", target_calendar_id=None
        )

    def test_moves_event_by_calendar_id_only(self, mock_service):
        cal = MockCalendar("Personal", "cal-p")
        start = MockNSDate(1742036400.0)
        end = MockNSDate(1742040000.0)
        evt = MockEvent(
            title="Moved event",
            identifier="evt-7",
            calendar=cal,
            start_date=start,
            end_date=end,
        )
        mock_service.move_event.return_value = evt

        result = move_event("evt-7", target_calendar_id="cal-p")

        assert result["id"] == "evt-7"
        assert result["calendar"] == "Personal"
        mock_service.move_event.assert_called_once_with(
            "evt-7", None, target_calendar_id="cal-p"
        )

    def test_moves_event_by_calendar_id(self, mock_service):
        cal = MockCalendar("Personal", "cal-p")
        start = MockNSDate(1742036400.0)
        end = MockNSDate(1742040000.0)
        evt = MockEvent(
            title="Moved event",
            identifier="evt-7",
            calendar=cal,
            start_date=start,
            end_date=end,
        )
        mock_service.move_event.return_value = evt

        result = move_event("evt-7", target_calendar_name="Personal", target_calendar_id="cal-p")

        assert result["id"] == "evt-7"
        assert result["calendar"] == "Personal"
        mock_service.move_event.assert_called_once_with(
            "evt-7", "Personal", target_calendar_id="cal-p"
        )

    def test_moves_event_by_calendar_id_with_name(self, mock_service):
        cal = MockCalendar("Personal", "cal-p")
        start = MockNSDate(1742036400.0)
        end = MockNSDate(1742040000.0)
        evt = MockEvent(
            title="Moved event",
            identifier="evt-7",
            calendar=cal,
            start_date=start,
            end_date=end,
        )
        mock_service.move_event.return_value = evt

        result = move_event("evt-7", target_calendar_name="Personal", target_calendar_id="cal-p")

        assert result["id"] == "evt-7"
        assert result["calendar"] == "Personal"
        mock_service.move_event.assert_called_once_with(
            "evt-7", "Personal", target_calendar_id="cal-p"
        )

    def test_event_not_found_propagates(self, mock_service):
        mock_service.move_event.side_effect = ValueError(
            "Event 'bad-id' not found"
        )

        with pytest.raises(ValueError, match="not found"):
            move_event("bad-id", target_calendar_name="Personal")

    def test_target_calendar_not_found_propagates(self, mock_service):
        mock_service.move_event.side_effect = ValueError(
            "Calendar 'Missing' not found"
        )

        with pytest.raises(ValueError, match="not found"):
            move_event("evt-7", target_calendar_name="Missing")


# ---------------------------------------------------------------------------
# Tests: quick_add
# ---------------------------------------------------------------------------


class TestQuickAdd:
    def test_creates_with_defaults(self, mock_service):
        cal = MockCalendar("Default")
        start = MockNSDate(1742036400.0)
        end = MockNSDate(1742040000.0)
        evt = MockEvent(
            title="Quick event",
            identifier="evt-8",
            calendar=cal,
            start_date=start,
            end_date=end,
        )
        mock_service.create_event.return_value = evt

        result = quick_add("Quick event", "2026-03-15T10:00:00")

        assert result["title"] == "Quick event"
        assert result["id"] == "evt-8"
        assert result["calendar"] == "Default"
        call_kwargs = mock_service.create_event.call_args.kwargs
        assert call_kwargs["title"] == "Quick event"
        assert call_kwargs["start_date"] == datetime(2026, 3, 15, 10, 0)
        assert call_kwargs["end_date"] == datetime(2026, 3, 15, 11, 0)
        assert call_kwargs["notes"] is None

    def test_with_notes(self, mock_service):
        cal = MockCalendar("Default")
        start = MockNSDate(1742036400.0)
        end = MockNSDate(1742040000.0)
        evt = MockEvent(
            title="Idea",
            identifier="evt-9",
            calendar=cal,
            start_date=start,
            end_date=end,
            notes="Some details",
        )
        mock_service.create_event.return_value = evt

        result = quick_add("Idea", "2026-03-15T10:00:00", notes="Some details")

        assert result["title"] == "Idea"
        assert result["notes"] == "Some details"
        call_kwargs = mock_service.create_event.call_args.kwargs
        assert call_kwargs["notes"] == "Some details"

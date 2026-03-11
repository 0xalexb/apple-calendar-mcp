from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from apple_calendar_mcp.eventkit_service import EventKitService


# ---------------------------------------------------------------------------
# Mock helpers
# ---------------------------------------------------------------------------


class MockCalendar:
    """Simulates an EKCalendar object."""

    def __init__(self, name: str, identifier: str = "cal-1"):
        self._title = name
        self._identifier = identifier
        self._source = MagicMock()

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


class MockNSDate:
    """Simulates an NSDate object."""

    def __init__(self, timestamp: float):
        self._timestamp = timestamp

    def timeIntervalSince1970(self):
        return self._timestamp


class MockEvent:
    """Simulates an EKEvent object."""

    def __init__(self, title: str = "", identifier: str = "evt-1"):
        self._title = title
        self._identifier = identifier
        self._calendar = None
        self._start_date = None
        self._end_date = None
        self._is_all_day = False
        self._location = None
        self._url = None
        self._notes = None
        self._recurrence_rules: list = []

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
        return bool(self._recurrence_rules)

    def addRecurrenceRule_(self, rule):
        self._recurrence_rules.append(rule)


def _make_ek_module():
    """Create a mock EventKit module with required constants and classes."""
    ek = MagicMock()
    ek.EKEntityTypeEvent = 0
    return ek


def _make_store(calendars=None, events=None):
    """Create a mock EKEventStore."""
    store = MagicMock()
    store.calendarsForEntityType_.return_value = calendars or []

    default_cal = MockCalendar("Default", "default-cal")
    store.defaultCalendarForNewEvents.return_value = default_cal

    store.eventsMatchingPredicate_.return_value = events
    store.saveCalendar_commit_error_.return_value = (True, None)
    store.saveEvent_span_commit_error_.return_value = (True, None)
    store.removeEvent_span_commit_error_.return_value = (True, None)
    return store


def _make_service(calendars=None, events=None, store=None, ek=None):
    """Create an EventKitService with mocked dependencies."""
    if ek is None:
        ek = _make_ek_module()
    if store is None:
        store = _make_store(calendars=calendars, events=events)
    return EventKitService(event_store=store, ek_module=ek), store, ek


# ---------------------------------------------------------------------------
# Tests: get_all_calendars
# ---------------------------------------------------------------------------


class TestGetAllCalendars:
    def test_returns_calendars(self):
        cals = [MockCalendar("Work"), MockCalendar("Personal")]
        svc, store, _ = _make_service(calendars=cals)

        result = svc.get_all_calendars()

        assert result == cals
        store.calendarsForEntityType_.assert_called_once_with(0)

    def test_returns_empty_when_none(self):
        svc, _, _ = _make_service(calendars=None)
        store = svc._store
        store.calendarsForEntityType_.return_value = None

        assert svc.get_all_calendars() == []

    def test_returns_empty_list(self):
        svc, _, _ = _make_service(calendars=[])
        assert svc.get_all_calendars() == []


# ---------------------------------------------------------------------------
# Tests: get_calendar_by_name
# ---------------------------------------------------------------------------


class TestGetCalendarByName:
    def test_found(self):
        work = MockCalendar("Work")
        personal = MockCalendar("Personal")
        svc, _, _ = _make_service(calendars=[work, personal])

        assert svc.get_calendar_by_name("Personal") is personal

    def test_not_found(self):
        svc, _, _ = _make_service(calendars=[MockCalendar("Work")])

        assert svc.get_calendar_by_name("Missing") is None


# ---------------------------------------------------------------------------
# Tests: get_calendar_by_id
# ---------------------------------------------------------------------------


class TestGetCalendarById:
    def test_found(self):
        work = MockCalendar("Work", "cal-work")
        personal = MockCalendar("Personal", "cal-personal")
        svc, _, _ = _make_service(calendars=[work, personal])

        assert svc.get_calendar_by_id("cal-personal") is personal

    def test_not_found(self):
        svc, _, _ = _make_service(calendars=[MockCalendar("Work", "cal-work")])

        assert svc.get_calendar_by_id("cal-missing") is None


# ---------------------------------------------------------------------------
# Tests: _resolve_calendar
# ---------------------------------------------------------------------------


class TestResolveCalendar:
    def test_resolve_by_id_preferred_over_name(self):
        work1 = MockCalendar("Work", "cal-w1")
        work2 = MockCalendar("Work", "cal-w2")
        svc, _, _ = _make_service(calendars=[work1, work2])

        result = svc._resolve_calendar(name="Work", calendar_id="cal-w2")
        assert result is work2

    def test_resolve_by_name_fallback(self):
        work = MockCalendar("Work", "cal-w1")
        svc, _, _ = _make_service(calendars=[work])

        result = svc._resolve_calendar(name="Work")
        assert result is work

    def test_resolve_by_id_only(self):
        work = MockCalendar("Work", "cal-w1")
        svc, _, _ = _make_service(calendars=[work])

        result = svc._resolve_calendar(calendar_id="cal-w1")
        assert result is work

    def test_id_not_found_raises(self):
        svc, _, _ = _make_service(calendars=[MockCalendar("Work", "cal-w1")])

        with pytest.raises(ValueError, match="Calendar with id 'cal-missing' not found"):
            svc._resolve_calendar(calendar_id="cal-missing")

    def test_name_not_found_raises(self):
        svc, _, _ = _make_service(calendars=[])

        with pytest.raises(ValueError, match="Calendar 'Missing' not found"):
            svc._resolve_calendar(name="Missing")

    def test_name_id_mismatch_raises(self):
        work = MockCalendar("Work", "cal-w1")
        svc, _, _ = _make_service(calendars=[work])

        with pytest.raises(
            ValueError, match="Calendar id 'cal-w1' resolves to 'Work', not 'Personal'"
        ):
            svc._resolve_calendar(name="Personal", calendar_id="cal-w1")

    def test_neither_provided_raises(self):
        svc, _, _ = _make_service()

        with pytest.raises(ValueError, match="Either calendar name or calendar_id"):
            svc._resolve_calendar()


# ---------------------------------------------------------------------------
# Tests: create_calendar
# ---------------------------------------------------------------------------


class TestCreateCalendar:
    def test_success(self):
        ek = _make_ek_module()
        mock_cal = MockCalendar("", "new-cal")
        ek.EKCalendar.calendarForEntityType_eventStore_.return_value = mock_cal
        store = _make_store()
        svc = EventKitService(event_store=store, ek_module=ek)

        result = svc.create_calendar("Work")

        assert result is mock_cal
        assert mock_cal.title() == "Work"
        store.saveCalendar_commit_error_.assert_called_once_with(
            mock_cal, True, None
        )

    def test_failure_raises(self):
        ek = _make_ek_module()
        mock_cal = MockCalendar("", "new-cal")
        ek.EKCalendar.calendarForEntityType_eventStore_.return_value = mock_cal
        store = _make_store()
        store.saveCalendar_commit_error_.return_value = (False, "save error")
        svc = EventKitService(event_store=store, ek_module=ek)

        with pytest.raises(RuntimeError, match="Failed to create calendar"):
            svc.create_calendar("Work")

    def test_no_default_calendar_raises(self):
        ek = _make_ek_module()
        store = _make_store()
        store.defaultCalendarForNewEvents.return_value = None
        svc = EventKitService(event_store=store, ek_module=ek)

        with pytest.raises(RuntimeError, match="No default calendar"):
            svc.create_calendar("Work")


# ---------------------------------------------------------------------------
# Tests: get_events
# ---------------------------------------------------------------------------


class TestGetEvents:
    def test_returns_events_for_calendar(self):
        cal = MockCalendar("Work")
        evt = MockEvent("Meeting")
        svc, store, _ = _make_service(calendars=[cal], events=[evt])

        mock_foundation = MagicMock()
        with patch.dict("sys.modules", {"Foundation": mock_foundation}):
            result = svc.get_events(
                "Work", datetime(2026, 3, 15), datetime(2026, 3, 16)
            )

        assert result == [evt]
        store.predicateForEventsWithStartDate_endDate_calendars_.assert_called_once()
        store.eventsMatchingPredicate_.assert_called_once()

    def test_calendar_not_found_raises(self):
        svc, _, _ = _make_service(calendars=[])

        with pytest.raises(ValueError, match="Calendar 'Missing' not found"):
            svc.get_events(
                "Missing", datetime(2026, 3, 15), datetime(2026, 3, 16)
            )

    def test_returns_empty_when_no_events(self):
        cal = MockCalendar("Work")
        svc, _, _ = _make_service(calendars=[cal], events=None)

        mock_foundation = MagicMock()
        with patch.dict("sys.modules", {"Foundation": mock_foundation}):
            result = svc.get_events(
                "Work", datetime(2026, 3, 15), datetime(2026, 3, 16)
            )

        assert result == []

    def test_by_calendar_id(self):
        cal1 = MockCalendar("Work", "cal-w1")
        cal2 = MockCalendar("Work", "cal-w2")
        evt = MockEvent("Meeting")
        svc, store, _ = _make_service(calendars=[cal1, cal2], events=[evt])

        mock_foundation = MagicMock()
        with patch.dict("sys.modules", {"Foundation": mock_foundation}):
            result = svc.get_events(
                None,
                datetime(2026, 3, 15),
                datetime(2026, 3, 16),
                calendar_id="cal-w2",
            )

        assert result == [evt]
        args = store.predicateForEventsWithStartDate_endDate_calendars_.call_args
        assert args[0][2] == [cal2]

    def test_calendar_id_not_found_raises(self):
        svc, _, _ = _make_service(calendars=[])

        with pytest.raises(ValueError, match="Calendar with id 'cal-bad' not found"):
            svc.get_events(
                None,
                datetime(2026, 3, 15),
                datetime(2026, 3, 16),
                calendar_id="cal-bad",
            )


# ---------------------------------------------------------------------------
# Tests: get_all_events
# ---------------------------------------------------------------------------


class TestGetAllEvents:
    def test_returns_all_events(self):
        cals = [MockCalendar("Work"), MockCalendar("Home")]
        evts = [MockEvent("Meeting"), MockEvent("Dinner")]
        svc, store, _ = _make_service(calendars=cals, events=evts)

        mock_foundation = MagicMock()
        with patch.dict("sys.modules", {"Foundation": mock_foundation}):
            result = svc.get_all_events(
                datetime(2026, 3, 15), datetime(2026, 3, 16)
            )

        assert result == evts
        store.predicateForEventsWithStartDate_endDate_calendars_.assert_called_once()
        store.eventsMatchingPredicate_.assert_called_once()

    def test_returns_empty_when_no_calendars(self):
        svc, _, _ = _make_service(calendars=[])

        result = svc.get_all_events(
            datetime(2026, 3, 15), datetime(2026, 3, 16)
        )

        assert result == []

    def test_returns_empty_when_no_events(self):
        cals = [MockCalendar("Work")]
        svc, _, _ = _make_service(calendars=cals, events=None)

        mock_foundation = MagicMock()
        with patch.dict("sys.modules", {"Foundation": mock_foundation}):
            result = svc.get_all_events(
                datetime(2026, 3, 15), datetime(2026, 3, 16)
            )

        assert result == []


# ---------------------------------------------------------------------------
# Tests: create_event
# ---------------------------------------------------------------------------


class TestCreateEvent:
    def test_basic_with_default_calendar(self):
        ek = _make_ek_module()
        mock_evt = MockEvent()
        ek.EKEvent.eventWithEventStore_.return_value = mock_evt
        store = _make_store()
        svc = EventKitService(event_store=store, ek_module=ek)

        mock_foundation = MagicMock()
        with patch.dict("sys.modules", {"Foundation": mock_foundation}):
            result = svc.create_event(
                "Meeting",
                start_date=datetime(2026, 3, 15, 10, 0),
                end_date=datetime(2026, 3, 15, 11, 0),
            )

        assert result is mock_evt
        assert mock_evt.title() == "Meeting"
        assert mock_evt.calendar() is store.defaultCalendarForNewEvents()
        store.saveEvent_span_commit_error_.assert_called_once_with(
            mock_evt, 0, True, None
        )

    def test_with_specific_calendar(self):
        ek = _make_ek_module()
        mock_evt = MockEvent()
        ek.EKEvent.eventWithEventStore_.return_value = mock_evt
        target_cal = MockCalendar("Work")
        store = _make_store(calendars=[target_cal])
        svc = EventKitService(event_store=store, ek_module=ek)

        mock_foundation = MagicMock()
        with patch.dict("sys.modules", {"Foundation": mock_foundation}):
            result = svc.create_event(
                "Meeting",
                start_date=datetime(2026, 3, 15, 10, 0),
                end_date=datetime(2026, 3, 15, 11, 0),
                calendar_name="Work",
            )

        assert result.calendar() is target_cal

    def test_with_all_options(self):
        ek = _make_ek_module()
        mock_evt = MockEvent()
        ek.EKEvent.eventWithEventStore_.return_value = mock_evt
        store = _make_store()
        svc = EventKitService(event_store=store, ek_module=ek)

        mock_foundation = MagicMock()
        with patch.dict("sys.modules", {"Foundation": mock_foundation}):
            svc.create_event(
                "Meeting",
                start_date=datetime(2026, 3, 15, 10, 0),
                end_date=datetime(2026, 3, 15, 11, 0),
                is_all_day=False,
                location="Office",
                url="https://example.com",
                notes="Bring slides",
            )

        assert mock_evt.location() == "Office"
        assert mock_evt.notes() == "Bring slides"
        assert mock_evt.isAllDay() is False

    def test_with_recurrence(self):
        ek = _make_ek_module()
        mock_evt = MockEvent()
        ek.EKEvent.eventWithEventStore_.return_value = mock_evt
        mock_rule = MagicMock()
        ek.EKRecurrenceRule.alloc().initRecurrenceWithFrequency_interval_end_.return_value = mock_rule
        store = _make_store()
        svc = EventKitService(event_store=store, ek_module=ek)

        mock_foundation = MagicMock()
        with patch.dict("sys.modules", {"Foundation": mock_foundation}):
            svc.create_event(
                "Standup",
                start_date=datetime(2026, 3, 15, 9, 0),
                end_date=datetime(2026, 3, 15, 9, 15),
                recurrence="daily",
            )

        assert mock_rule in mock_evt._recurrence_rules

    def test_with_calendar_id(self):
        ek = _make_ek_module()
        mock_evt = MockEvent()
        ek.EKEvent.eventWithEventStore_.return_value = mock_evt
        target_cal = MockCalendar("Work", "cal-w2")
        other_cal = MockCalendar("Work", "cal-w1")
        store = _make_store(calendars=[other_cal, target_cal])
        svc = EventKitService(event_store=store, ek_module=ek)

        mock_foundation = MagicMock()
        with patch.dict("sys.modules", {"Foundation": mock_foundation}):
            result = svc.create_event(
                "Meeting",
                start_date=datetime(2026, 3, 15, 10, 0),
                end_date=datetime(2026, 3, 15, 11, 0),
                calendar_id="cal-w2",
            )

        assert result.calendar() is target_cal

    def test_calendar_not_found_raises(self):
        ek = _make_ek_module()
        mock_evt = MockEvent()
        ek.EKEvent.eventWithEventStore_.return_value = mock_evt
        store = _make_store(calendars=[])
        svc = EventKitService(event_store=store, ek_module=ek)

        mock_foundation = MagicMock()
        with patch.dict("sys.modules", {"Foundation": mock_foundation}):
            with pytest.raises(
                ValueError, match="Calendar 'NonExistent' not found"
            ):
                svc.create_event(
                    "Task",
                    start_date=datetime(2026, 3, 15, 10, 0),
                    end_date=datetime(2026, 3, 15, 11, 0),
                    calendar_name="NonExistent",
                )

    def test_save_failure_raises(self):
        ek = _make_ek_module()
        mock_evt = MockEvent()
        ek.EKEvent.eventWithEventStore_.return_value = mock_evt
        store = _make_store()
        store.saveEvent_span_commit_error_.return_value = (False, "disk full")
        svc = EventKitService(event_store=store, ek_module=ek)

        mock_foundation = MagicMock()
        with patch.dict("sys.modules", {"Foundation": mock_foundation}):
            with pytest.raises(RuntimeError, match="Failed to create event"):
                svc.create_event(
                    "Task",
                    start_date=datetime(2026, 3, 15, 10, 0),
                    end_date=datetime(2026, 3, 15, 11, 0),
                )

    def test_no_default_calendar_raises(self):
        ek = _make_ek_module()
        mock_evt = MockEvent()
        ek.EKEvent.eventWithEventStore_.return_value = mock_evt
        store = _make_store()
        store.defaultCalendarForNewEvents.return_value = None
        svc = EventKitService(event_store=store, ek_module=ek)

        mock_foundation = MagicMock()
        with patch.dict("sys.modules", {"Foundation": mock_foundation}):
            with pytest.raises(RuntimeError, match="No default calendar"):
                svc.create_event(
                    "Task",
                    start_date=datetime(2026, 3, 15, 10, 0),
                    end_date=datetime(2026, 3, 15, 11, 0),
                )

    def test_all_day_event(self):
        ek = _make_ek_module()
        mock_evt = MockEvent()
        ek.EKEvent.eventWithEventStore_.return_value = mock_evt
        store = _make_store()
        svc = EventKitService(event_store=store, ek_module=ek)

        mock_foundation = MagicMock()
        with patch.dict("sys.modules", {"Foundation": mock_foundation}):
            svc.create_event(
                "Holiday",
                start_date=datetime(2026, 3, 15),
                end_date=datetime(2026, 3, 16),
                is_all_day=True,
            )

        assert mock_evt.isAllDay() is True


# ---------------------------------------------------------------------------
# Tests: update_event
# ---------------------------------------------------------------------------


class TestUpdateEvent:
    def test_update_title(self):
        mock_evt = MockEvent("Old Title", "evt-42")
        store = _make_store()
        store.calendarItemWithIdentifier_.return_value = mock_evt
        svc, _, _ = _make_service(store=store)

        result = svc.update_event("evt-42", title="New Title")

        assert result is mock_evt
        assert mock_evt.title() == "New Title"
        store.saveEvent_span_commit_error_.assert_called_once_with(
            mock_evt, 0, True, None
        )

    def test_update_multiple_fields(self):
        mock_evt = MockEvent("Meeting", "evt-42")
        store = _make_store()
        store.calendarItemWithIdentifier_.return_value = mock_evt
        svc, _, _ = _make_service(store=store)

        mock_foundation = MagicMock()
        with patch.dict("sys.modules", {"Foundation": mock_foundation}):
            svc.update_event(
                "evt-42",
                title="Updated Meeting",
                location="Room 2",
                notes="Updated notes",
                is_all_day=True,
            )

        assert mock_evt.title() == "Updated Meeting"
        assert mock_evt.location() == "Room 2"
        assert mock_evt.notes() == "Updated notes"
        assert mock_evt.isAllDay() is True

    def test_not_found_raises(self):
        store = _make_store()
        store.calendarItemWithIdentifier_.return_value = None
        svc, _, _ = _make_service(store=store)

        with pytest.raises(ValueError, match="Event 'evt-99' not found"):
            svc.update_event("evt-99", title="New")

    def test_save_failure_raises(self):
        mock_evt = MockEvent("Meeting", "evt-42")
        store = _make_store()
        store.calendarItemWithIdentifier_.return_value = mock_evt
        store.saveEvent_span_commit_error_.return_value = (False, "err")
        svc, _, _ = _make_service(store=store)

        with pytest.raises(RuntimeError, match="Failed to update event"):
            svc.update_event("evt-42", title="New")

    def test_no_changes(self):
        mock_evt = MockEvent("Meeting", "evt-42")
        store = _make_store()
        store.calendarItemWithIdentifier_.return_value = mock_evt
        svc, _, _ = _make_service(store=store)

        result = svc.update_event("evt-42")

        assert result is mock_evt
        assert mock_evt.title() == "Meeting"

    def test_update_url(self):
        mock_evt = MockEvent("Meeting", "evt-42")
        store = _make_store()
        store.calendarItemWithIdentifier_.return_value = mock_evt
        svc, _, _ = _make_service(store=store)

        mock_foundation = MagicMock()
        with patch.dict("sys.modules", {"Foundation": mock_foundation}):
            svc.update_event("evt-42", url="https://example.com")

        mock_foundation.NSURL.URLWithString_.assert_called_once_with(
            "https://example.com"
        )

    def test_update_dates(self):
        mock_evt = MockEvent("Meeting", "evt-42")
        store = _make_store()
        store.calendarItemWithIdentifier_.return_value = mock_evt
        svc, _, _ = _make_service(store=store)

        mock_foundation = MagicMock()
        with patch.dict("sys.modules", {"Foundation": mock_foundation}):
            svc.update_event(
                "evt-42",
                start_date=datetime(2026, 3, 20, 14, 0),
                end_date=datetime(2026, 3, 20, 15, 0),
            )

        assert mock_foundation.NSDate.dateWithTimeIntervalSince1970_.call_count == 2

    def test_clear_location_with_empty_string(self):
        mock_evt = MockEvent("Meeting", "evt-42")
        mock_evt._location = "Office"
        store = _make_store()
        store.calendarItemWithIdentifier_.return_value = mock_evt
        svc, _, _ = _make_service(store=store)

        svc.update_event("evt-42", location="")

        assert mock_evt.location() is None

    def test_clear_notes_with_empty_string(self):
        mock_evt = MockEvent("Meeting", "evt-42")
        mock_evt._notes = "Some notes"
        store = _make_store()
        store.calendarItemWithIdentifier_.return_value = mock_evt
        svc, _, _ = _make_service(store=store)

        svc.update_event("evt-42", notes="")

        assert mock_evt.notes() is None

    def test_clear_url_with_empty_string(self):
        mock_evt = MockEvent("Meeting", "evt-42")
        mock_evt._url = MagicMock()
        store = _make_store()
        store.calendarItemWithIdentifier_.return_value = mock_evt
        svc, _, _ = _make_service(store=store)

        svc.update_event("evt-42", url="")

        assert mock_evt.URL() is None


# ---------------------------------------------------------------------------
# Tests: delete_event
# ---------------------------------------------------------------------------


class TestDeleteEvent:
    def test_success_this_span(self):
        mock_evt = MockEvent("Meeting", "evt-42")
        store = _make_store()
        store.calendarItemWithIdentifier_.return_value = mock_evt
        svc, _, _ = _make_service(store=store)

        svc.delete_event("evt-42")

        store.removeEvent_span_commit_error_.assert_called_once_with(
            mock_evt, 0, True, None
        )

    def test_success_future_span(self):
        mock_evt = MockEvent("Meeting", "evt-42")
        store = _make_store()
        store.calendarItemWithIdentifier_.return_value = mock_evt
        svc, _, _ = _make_service(store=store)

        svc.delete_event("evt-42", span="future")

        store.removeEvent_span_commit_error_.assert_called_once_with(
            mock_evt, 1, True, None
        )

    def test_not_found_raises(self):
        store = _make_store()
        store.calendarItemWithIdentifier_.return_value = None
        svc, _, _ = _make_service(store=store)

        with pytest.raises(ValueError, match="Event 'evt-99' not found"):
            svc.delete_event("evt-99")

    def test_invalid_span_raises(self):
        mock_evt = MockEvent("Meeting", "evt-42")
        store = _make_store()
        store.calendarItemWithIdentifier_.return_value = mock_evt
        svc, _, _ = _make_service(store=store)

        with pytest.raises(ValueError, match="Invalid span 'all'"):
            svc.delete_event("evt-42", span="all")

    def test_remove_failure_raises(self):
        mock_evt = MockEvent("Meeting", "evt-42")
        store = _make_store()
        store.calendarItemWithIdentifier_.return_value = mock_evt
        store.removeEvent_span_commit_error_.return_value = (False, "err")
        svc, _, _ = _make_service(store=store)

        with pytest.raises(RuntimeError, match="Failed to delete event"):
            svc.delete_event("evt-42")


# ---------------------------------------------------------------------------
# Tests: move_event
# ---------------------------------------------------------------------------


class TestMoveEvent:
    def test_success(self):
        mock_evt = MockEvent("Meeting", "evt-42")
        target_cal = MockCalendar("Personal", "cal-2")
        store = _make_store(calendars=[target_cal])
        store.calendarItemWithIdentifier_.return_value = mock_evt
        svc, _, _ = _make_service(store=store)

        result = svc.move_event("evt-42", "Personal")

        assert result is mock_evt
        assert mock_evt.calendar() is target_cal
        store.saveEvent_span_commit_error_.assert_called_once_with(
            mock_evt, 0, True, None
        )

    def test_success_by_calendar_id(self):
        mock_evt = MockEvent("Meeting", "evt-42")
        target_cal = MockCalendar("Work", "cal-w2")
        other_cal = MockCalendar("Work", "cal-w1")
        store = _make_store(calendars=[other_cal, target_cal])
        store.calendarItemWithIdentifier_.return_value = mock_evt
        svc, _, _ = _make_service(store=store)

        result = svc.move_event("evt-42", target_calendar_id="cal-w2")

        assert result is mock_evt
        assert mock_evt.calendar() is target_cal

    def test_event_not_found_raises(self):
        store = _make_store(calendars=[MockCalendar("Personal")])
        store.calendarItemWithIdentifier_.return_value = None
        svc, _, _ = _make_service(store=store)

        with pytest.raises(ValueError, match="Event 'evt-99' not found"):
            svc.move_event("evt-99", "Personal")

    def test_target_calendar_not_found_raises(self):
        mock_evt = MockEvent("Meeting", "evt-42")
        store = _make_store(calendars=[])
        store.calendarItemWithIdentifier_.return_value = mock_evt
        svc, _, _ = _make_service(store=store)

        with pytest.raises(ValueError, match="Calendar 'Missing' not found"):
            svc.move_event("evt-42", "Missing")

    def test_save_failure_raises(self):
        mock_evt = MockEvent("Meeting", "evt-42")
        target_cal = MockCalendar("Personal")
        store = _make_store(calendars=[target_cal])
        store.calendarItemWithIdentifier_.return_value = mock_evt
        store.saveEvent_span_commit_error_.return_value = (False, "err")
        svc, _, _ = _make_service(store=store)

        with pytest.raises(RuntimeError, match="Failed to move event"):
            svc.move_event("evt-42", "Personal")


# ---------------------------------------------------------------------------
# Tests: _find_event_by_id
# ---------------------------------------------------------------------------


class TestFindEventById:
    def test_found(self):
        mock_evt = MockEvent("Meeting", "evt-42")
        store = _make_store()
        store.calendarItemWithIdentifier_.return_value = mock_evt
        svc, _, _ = _make_service(store=store)

        assert svc._find_event_by_id("evt-42") is mock_evt
        store.calendarItemWithIdentifier_.assert_called_once_with("evt-42")

    def test_not_found(self):
        store = _make_store()
        store.calendarItemWithIdentifier_.return_value = None
        svc, _, _ = _make_service(store=store)

        assert svc._find_event_by_id("missing") is None


# ---------------------------------------------------------------------------
# Tests: _create_recurrence_rule
# ---------------------------------------------------------------------------


class TestCreateRecurrenceRule:
    @pytest.mark.parametrize(
        "recurrence,freq",
        [
            ("daily", 0),
            ("weekly", 1),
            ("monthly", 2),
            ("yearly", 3),
            ("Daily", 0),
            ("WEEKLY", 1),
        ],
    )
    def test_valid_recurrence(self, recurrence, freq):
        ek = _make_ek_module()
        mock_rule = MagicMock()
        ek.EKRecurrenceRule.alloc().initRecurrenceWithFrequency_interval_end_.return_value = mock_rule
        svc = EventKitService(event_store=_make_store(), ek_module=ek)

        result = svc._create_recurrence_rule(recurrence)

        assert result is mock_rule
        ek.EKRecurrenceRule.alloc().initRecurrenceWithFrequency_interval_end_.assert_called_with(
            freq, 1, None
        )

    def test_invalid_recurrence_raises(self):
        svc, _, _ = _make_service()
        with pytest.raises(ValueError, match="Invalid recurrence"):
            svc._create_recurrence_rule("biweekly")


# ---------------------------------------------------------------------------
# Tests: _datetime_to_nsdate
# ---------------------------------------------------------------------------


class TestDatetimeToNsdate:
    def test_converts_naive_datetime(self):
        svc, _, _ = _make_service()

        mock_foundation = MagicMock()
        mock_nsdate = MockNSDate(1742036400.0)
        mock_foundation.NSDate.dateWithTimeIntervalSince1970_.return_value = (
            mock_nsdate
        )

        dt = datetime(2026, 3, 15, 10, 0)
        with patch.dict("sys.modules", {"Foundation": mock_foundation}):
            result = svc._datetime_to_nsdate(dt)

        assert result is mock_nsdate
        mock_foundation.NSDate.dateWithTimeIntervalSince1970_.assert_called_once_with(
            dt.timestamp()
        )

    def test_converts_timezone_aware_datetime(self):
        svc, _, _ = _make_service()

        mock_foundation = MagicMock()
        mock_nsdate = MockNSDate(1742036400.0)
        mock_foundation.NSDate.dateWithTimeIntervalSince1970_.return_value = (
            mock_nsdate
        )

        dt = datetime(2026, 3, 15, 10, 0, tzinfo=timezone.utc)
        with patch.dict("sys.modules", {"Foundation": mock_foundation}):
            result = svc._datetime_to_nsdate(dt)

        assert result is mock_nsdate


# ---------------------------------------------------------------------------
# Tests: _nsdate_to_datetime
# ---------------------------------------------------------------------------


class TestNsdateToDatetime:
    def test_converts_nsdate(self):
        svc, _, _ = _make_service()
        nsdate = MockNSDate(1742036400.0)

        result = svc._nsdate_to_datetime(nsdate)

        assert isinstance(result, datetime)
        assert result == datetime.fromtimestamp(1742036400.0)


# ---------------------------------------------------------------------------
# Tests: _make_nsurl
# ---------------------------------------------------------------------------


class TestMakeNsurl:
    def test_creates_nsurl(self):
        svc, _, _ = _make_service()

        mock_foundation = MagicMock()
        mock_url = MagicMock()
        mock_foundation.NSURL.URLWithString_.return_value = mock_url

        with patch.dict("sys.modules", {"Foundation": mock_foundation}):
            result = svc._make_nsurl("https://example.com")

        assert result is mock_url
        mock_foundation.NSURL.URLWithString_.assert_called_once_with(
            "https://example.com"
        )

    def test_malformed_url_raises(self):
        svc, _, _ = _make_service()

        mock_foundation = MagicMock()
        mock_foundation.NSURL.URLWithString_.return_value = None

        with patch.dict("sys.modules", {"Foundation": mock_foundation}):
            with pytest.raises(ValueError, match="Invalid URL"):
                svc._make_nsurl("not a valid url")

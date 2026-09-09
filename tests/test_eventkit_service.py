from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from apple_calendar_mcp.eventkit_service import EventKitService
from tests.conftest import (
    MockCalendar,
    MockEvent,
    MockNSDate,
    make_ek_module,
    make_store,
)


def _make_service(calendars=None, events=None, store=None, ek=None):
    """Create an EventKitService with mocked dependencies."""
    if ek is None:
        ek = make_ek_module()
    if store is None:
        store = make_store(calendars=calendars, events=events)
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
        ek = make_ek_module()
        mock_cal = MockCalendar("", "new-cal")
        ek.EKCalendar.calendarForEntityType_eventStore_.return_value = mock_cal
        store = make_store()
        svc = EventKitService(event_store=store, ek_module=ek)

        result = svc.create_calendar("Work")

        assert result is mock_cal
        assert mock_cal.title() == "Work"
        store.saveCalendar_commit_error_.assert_called_once_with(
            mock_cal, True, None
        )

    def test_failure_raises(self):
        ek = make_ek_module()
        mock_cal = MockCalendar("", "new-cal")
        ek.EKCalendar.calendarForEntityType_eventStore_.return_value = mock_cal
        store = make_store()
        store.saveCalendar_commit_error_.return_value = (False, "save error")
        svc = EventKitService(event_store=store, ek_module=ek)

        with pytest.raises(RuntimeError, match="Failed to create calendar"):
            svc.create_calendar("Work")

    def test_no_default_calendar_raises(self):
        ek = make_ek_module()
        store = make_store()
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
        ek = make_ek_module()
        mock_evt = MockEvent()
        ek.EKEvent.eventWithEventStore_.return_value = mock_evt
        store = make_store()
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
        ek = make_ek_module()
        mock_evt = MockEvent()
        ek.EKEvent.eventWithEventStore_.return_value = mock_evt
        target_cal = MockCalendar("Work")
        store = make_store(calendars=[target_cal])
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
        ek = make_ek_module()
        mock_evt = MockEvent()
        ek.EKEvent.eventWithEventStore_.return_value = mock_evt
        store = make_store()
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
        ek = make_ek_module()
        mock_evt = MockEvent()
        ek.EKEvent.eventWithEventStore_.return_value = mock_evt
        mock_rule = MagicMock()
        _rule_builder(ek).return_value = mock_rule
        store = make_store()
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
        ek = make_ek_module()
        mock_evt = MockEvent()
        ek.EKEvent.eventWithEventStore_.return_value = mock_evt
        target_cal = MockCalendar("Work", "cal-w2")
        other_cal = MockCalendar("Work", "cal-w1")
        store = make_store(calendars=[other_cal, target_cal])
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
        ek = make_ek_module()
        mock_evt = MockEvent()
        ek.EKEvent.eventWithEventStore_.return_value = mock_evt
        store = make_store(calendars=[])
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
        ek = make_ek_module()
        mock_evt = MockEvent()
        ek.EKEvent.eventWithEventStore_.return_value = mock_evt
        store = make_store()
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
        ek = make_ek_module()
        mock_evt = MockEvent()
        ek.EKEvent.eventWithEventStore_.return_value = mock_evt
        store = make_store()
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
        ek = make_ek_module()
        mock_evt = MockEvent()
        ek.EKEvent.eventWithEventStore_.return_value = mock_evt
        store = make_store()
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
        store = make_store()
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
        store = make_store()
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
        store = make_store()
        store.calendarItemWithIdentifier_.return_value = None
        svc, _, _ = _make_service(store=store)

        with pytest.raises(ValueError, match="Event 'evt-99' not found"):
            svc.update_event("evt-99", title="New")

    def test_save_failure_raises(self):
        mock_evt = MockEvent("Meeting", "evt-42")
        store = make_store()
        store.calendarItemWithIdentifier_.return_value = mock_evt
        store.saveEvent_span_commit_error_.return_value = (False, "err")
        svc, _, _ = _make_service(store=store)

        with pytest.raises(RuntimeError, match="Failed to update event"):
            svc.update_event("evt-42", title="New")

    def test_no_changes(self):
        mock_evt = MockEvent("Meeting", "evt-42")
        store = make_store()
        store.calendarItemWithIdentifier_.return_value = mock_evt
        svc, _, _ = _make_service(store=store)

        result = svc.update_event("evt-42")

        assert result is mock_evt
        assert mock_evt.title() == "Meeting"

    def test_update_url(self):
        mock_evt = MockEvent("Meeting", "evt-42")
        store = make_store()
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
        store = make_store()
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
        store = make_store()
        store.calendarItemWithIdentifier_.return_value = mock_evt
        svc, _, _ = _make_service(store=store)

        svc.update_event("evt-42", location="")

        assert mock_evt.location() is None

    def test_clear_notes_with_empty_string(self):
        mock_evt = MockEvent("Meeting", "evt-42")
        mock_evt._notes = "Some notes"
        store = make_store()
        store.calendarItemWithIdentifier_.return_value = mock_evt
        svc, _, _ = _make_service(store=store)

        svc.update_event("evt-42", notes="")

        assert mock_evt.notes() is None

    def test_clear_url_with_empty_string(self):
        mock_evt = MockEvent("Meeting", "evt-42")
        mock_evt._url = MagicMock()
        store = make_store()
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
        store = make_store()
        store.calendarItemWithIdentifier_.return_value = mock_evt
        svc, _, _ = _make_service(store=store)

        svc.delete_event("evt-42")

        store.removeEvent_span_commit_error_.assert_called_once_with(
            mock_evt, 0, True, None
        )

    def test_success_future_span(self):
        mock_evt = MockEvent("Meeting", "evt-42")
        store = make_store()
        store.calendarItemWithIdentifier_.return_value = mock_evt
        svc, _, _ = _make_service(store=store)

        svc.delete_event("evt-42", span="future")

        store.removeEvent_span_commit_error_.assert_called_once_with(
            mock_evt, 1, True, None
        )

    def test_not_found_raises(self):
        store = make_store()
        store.calendarItemWithIdentifier_.return_value = None
        svc, _, _ = _make_service(store=store)

        with pytest.raises(ValueError, match="Event 'evt-99' not found"):
            svc.delete_event("evt-99")

    def test_invalid_span_raises(self):
        mock_evt = MockEvent("Meeting", "evt-42")
        store = make_store()
        store.calendarItemWithIdentifier_.return_value = mock_evt
        svc, _, _ = _make_service(store=store)

        with pytest.raises(ValueError, match="Invalid span 'all'"):
            svc.delete_event("evt-42", span="all")

    def test_remove_failure_raises(self):
        mock_evt = MockEvent("Meeting", "evt-42")
        store = make_store()
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
        store = make_store(calendars=[target_cal])
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
        store = make_store(calendars=[other_cal, target_cal])
        store.calendarItemWithIdentifier_.return_value = mock_evt
        svc, _, _ = _make_service(store=store)

        result = svc.move_event("evt-42", target_calendar_id="cal-w2")

        assert result is mock_evt
        assert mock_evt.calendar() is target_cal

    def test_event_not_found_raises(self):
        store = make_store(calendars=[MockCalendar("Personal")])
        store.calendarItemWithIdentifier_.return_value = None
        svc, _, _ = _make_service(store=store)

        with pytest.raises(ValueError, match="Event 'evt-99' not found"):
            svc.move_event("evt-99", "Personal")

    def test_target_calendar_not_found_raises(self):
        mock_evt = MockEvent("Meeting", "evt-42")
        store = make_store(calendars=[])
        store.calendarItemWithIdentifier_.return_value = mock_evt
        svc, _, _ = _make_service(store=store)

        with pytest.raises(ValueError, match="Calendar 'Missing' not found"):
            svc.move_event("evt-42", "Missing")

    def test_save_failure_raises(self):
        mock_evt = MockEvent("Meeting", "evt-42")
        target_cal = MockCalendar("Personal")
        store = make_store(calendars=[target_cal])
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
        store = make_store()
        store.calendarItemWithIdentifier_.return_value = mock_evt
        svc, _, _ = _make_service(store=store)

        assert svc._find_event_by_id("evt-42") is mock_evt
        store.calendarItemWithIdentifier_.assert_called_once_with("evt-42")

    def test_not_found(self):
        store = make_store()
        store.calendarItemWithIdentifier_.return_value = None
        svc, _, _ = _make_service(store=store)

        assert svc._find_event_by_id("missing") is None


# ---------------------------------------------------------------------------
# Tests: _create_recurrence_rule
# ---------------------------------------------------------------------------


def _rule_builder(ek):
    """The full EKRecurrenceRule initializer on a mock EventKit module."""
    return (
        ek.EKRecurrenceRule.alloc().initRecurrenceWithFrequency_interval_daysOfTheWeek_daysOfTheMonth_monthsOfTheYear_weeksOfTheYear_daysOfTheYear_setPositions_end_
    )


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
        ek = make_ek_module()
        mock_rule = MagicMock()
        builder = _rule_builder(ek)
        builder.return_value = mock_rule
        svc = EventKitService(event_store=make_store(), ek_module=ek)

        result = svc._create_recurrence_rule(recurrence)

        assert result is mock_rule
        builder.assert_called_with(
            freq, 1, None, None, None, None, None, None, None
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


# ---------------------------------------------------------------------------
# Tests: availability, time zone, and alarms
# ---------------------------------------------------------------------------


def _service_with_event(event, store=None):
    """Build a service whose EKEvent factory returns the given mock event."""
    ek = make_ek_module()
    ek.EKEvent.eventWithEventStore_.return_value = event
    store = store or make_store()
    return EventKitService(event_store=store, ek_module=ek), store, ek


class TestAvailability:
    @pytest.mark.parametrize(
        "name,value",
        [("busy", 0), ("free", 1), ("tentative", 2), ("unavailable", 3)],
    )
    def test_create_sets_availability(self, name, value):
        event = MockEvent()
        svc, _, _ = _service_with_event(event)

        with patch.dict("sys.modules", {"Foundation": MagicMock()}):
            svc.create_event(
                "Focus",
                start_date=datetime(2026, 3, 15, 9, 0),
                end_date=datetime(2026, 3, 15, 10, 0),
                availability=name,
            )

        assert event.availability() == value

    def test_invalid_availability_raises(self):
        event = MockEvent()
        svc, _, _ = _service_with_event(event)

        with patch.dict("sys.modules", {"Foundation": MagicMock()}):
            with pytest.raises(ValueError, match="Invalid availability"):
                svc.create_event(
                    "Focus",
                    start_date=datetime(2026, 3, 15, 9, 0),
                    end_date=datetime(2026, 3, 15, 10, 0),
                    availability="maybe",
                )


class TestTimeZone:
    def test_create_sets_time_zone(self):
        event = MockEvent()
        svc, _, _ = _service_with_event(event)

        foundation = MagicMock()
        zone = MagicMock()
        foundation.NSTimeZone.timeZoneWithName_.return_value = zone
        with patch.dict("sys.modules", {"Foundation": foundation}):
            svc.create_event(
                "Call",
                start_date=datetime(2026, 3, 15, 9, 0),
                end_date=datetime(2026, 3, 15, 10, 0),
                time_zone="Europe/Berlin",
            )

        foundation.NSTimeZone.timeZoneWithName_.assert_called_with(
            "Europe/Berlin"
        )
        assert event.timeZone() is zone

    def test_invalid_time_zone_raises(self):
        event = MockEvent()
        svc, _, _ = _service_with_event(event)

        foundation = MagicMock()
        foundation.NSTimeZone.timeZoneWithName_.return_value = None
        with patch.dict("sys.modules", {"Foundation": foundation}):
            with pytest.raises(ValueError, match="Invalid time zone"):
                svc.create_event(
                    "Call",
                    start_date=datetime(2026, 3, 15, 9, 0),
                    end_date=datetime(2026, 3, 15, 10, 0),
                    time_zone="Mars/Olympus",
                )


class TestAlarms:
    def test_minutes_converted_to_negative_seconds(self):
        event = MockEvent()
        svc, _, ek = _service_with_event(event)

        with patch.dict("sys.modules", {"Foundation": MagicMock()}):
            svc.create_event(
                "Standup",
                start_date=datetime(2026, 3, 15, 9, 0),
                end_date=datetime(2026, 3, 15, 9, 15),
                alarm_minutes_before=[10, 60],
            )

        calls = ek.EKAlarm.alarmWithRelativeOffset_.call_args_list
        assert [call.args[0] for call in calls] == [-600, -3600]
        assert len(event.alarms()) == 2

    def test_empty_list_clears_alarms(self):
        event = MockEvent(alarms=[object()])
        store = make_store()
        store.calendarItemWithIdentifier_.return_value = event
        svc, _, _ = _service_with_event(MockEvent(), store=store)

        with patch.dict("sys.modules", {"Foundation": MagicMock()}):
            svc.update_event("evt-1", alarm_minutes_before=[])

        assert event.alarms() is None


# ---------------------------------------------------------------------------
# Tests: structured recurrence
# ---------------------------------------------------------------------------


class TestStructuredRecurrence:
    def test_string_and_dict_are_equivalent(self):
        ek = make_ek_module()
        svc = EventKitService(event_store=make_store(), ek_module=ek)

        svc._create_recurrence_rule("weekly")
        from_string = _rule_builder(ek).call_args
        svc._create_recurrence_rule({"frequency": "weekly"})
        from_dict = _rule_builder(ek).call_args

        assert from_string == from_dict

    def test_interval(self):
        ek = make_ek_module()
        svc = EventKitService(event_store=make_store(), ek_module=ek)

        svc._create_recurrence_rule({"frequency": "weekly", "interval": 3})

        assert _rule_builder(ek).call_args.args[1] == 3

    def test_days_of_week(self):
        ek = make_ek_module()
        svc = EventKitService(event_store=make_store(), ek_module=ek)

        svc._create_recurrence_rule(
            {"frequency": "weekly", "days_of_week": ["monday", "thursday"]}
        )

        calls = ek.EKRecurrenceDayOfWeek.dayOfWeek_.call_args_list
        assert [call.args[0] for call in calls] == [2, 5]
        assert _rule_builder(ek).call_args.args[2] is not None

    def test_invalid_weekday_raises(self):
        svc, _, _ = _make_service()
        with pytest.raises(ValueError, match="Invalid weekday"):
            svc._create_recurrence_rule(
                {"frequency": "weekly", "days_of_week": ["moonday"]}
            )

    def test_end_date(self):
        ek = make_ek_module()
        svc = EventKitService(event_store=make_store(), ek_module=ek)
        end = MagicMock()
        ek.EKRecurrenceEnd.recurrenceEndWithEndDate_.return_value = end

        with patch.dict("sys.modules", {"Foundation": MagicMock()}):
            svc._create_recurrence_rule(
                {"frequency": "daily", "end_date": "2026-12-31"}
            )

        assert _rule_builder(ek).call_args.args[8] is end

    def test_count(self):
        ek = make_ek_module()
        svc = EventKitService(event_store=make_store(), ek_module=ek)
        end = MagicMock()
        ek.EKRecurrenceEnd.recurrenceEndWithOccurrenceCount_.return_value = end

        svc._create_recurrence_rule({"frequency": "daily", "count": 10})

        ek.EKRecurrenceEnd.recurrenceEndWithOccurrenceCount_.assert_called_with(
            10
        )
        assert _rule_builder(ek).call_args.args[8] is end

    def test_end_date_and_count_together_raise(self):
        svc, _, _ = _make_service()
        with pytest.raises(ValueError, match="not both"):
            svc._create_recurrence_rule(
                {"frequency": "daily", "end_date": "2026-12-31", "count": 10}
            )

    def test_missing_frequency_raises(self):
        svc, _, _ = _make_service()
        with pytest.raises(ValueError, match="requires a 'frequency'"):
            svc._create_recurrence_rule({"interval": 2})

    def test_update_clears_recurrence(self):
        event = MockEvent(recurrence_rules=[object()])
        store = make_store()
        store.calendarItemWithIdentifier_.return_value = event
        svc, _, _ = _service_with_event(MockEvent(), store=store)

        with patch.dict("sys.modules", {"Foundation": MagicMock()}):
            svc.update_event("evt-1", recurrence="")

        assert event.recurrenceRules() == []


# ---------------------------------------------------------------------------
# Tests: update_event span
# ---------------------------------------------------------------------------


class TestUpdateEventSpan:
    @pytest.mark.parametrize("span,value", [("this", 0), ("future", 1)])
    def test_span_reaches_store(self, span, value):
        event = MockEvent()
        store = make_store()
        store.calendarItemWithIdentifier_.return_value = event
        svc, _, _ = _service_with_event(MockEvent(), store=store)

        with patch.dict("sys.modules", {"Foundation": MagicMock()}):
            svc.update_event("evt-1", title="Renamed", span=span)

        assert store.saveEvent_span_commit_error_.call_args.args[1] == value

    def test_default_span_is_this_event(self):
        event = MockEvent()
        store = make_store()
        store.calendarItemWithIdentifier_.return_value = event
        svc, _, _ = _service_with_event(MockEvent(), store=store)

        with patch.dict("sys.modules", {"Foundation": MagicMock()}):
            svc.update_event("evt-1", title="Renamed")

        assert store.saveEvent_span_commit_error_.call_args.args[1] == 0

    def test_invalid_span_raises(self):
        event = MockEvent()
        store = make_store()
        store.calendarItemWithIdentifier_.return_value = event
        svc, _, _ = _service_with_event(MockEvent(), store=store)

        with patch.dict("sys.modules", {"Foundation": MagicMock()}):
            with pytest.raises(ValueError, match="Invalid span"):
                svc.update_event("evt-1", title="Renamed", span="all")


# ---------------------------------------------------------------------------
# Tests: occurrence lookup
# ---------------------------------------------------------------------------


class TestFindEventById:
    def test_bare_identifier_uses_store_lookup(self):
        event = MockEvent(identifier="evt-1")
        store = make_store()
        store.calendarItemWithIdentifier_.return_value = event
        svc, _, _ = _service_with_event(MockEvent(), store=store)

        assert svc._find_event_by_id("evt-1") is event
        store.calendarItemWithIdentifier_.assert_called_with("evt-1")

    def test_missing_identifier_returns_none(self):
        store = make_store()
        store.calendarItemWithIdentifier_.return_value = None
        svc, _, _ = _service_with_event(MockEvent(), store=store)

        assert svc._find_event_by_id("nope") is None

    def test_composite_id_selects_the_matching_occurrence(self):
        cal = MockCalendar("Work", "cal-w")
        target = datetime(2026, 3, 15, 9, 0)
        first = MockEvent(
            identifier="evt-r",
            calendar=cal,
            occurrence_date=MockNSDate(
                datetime(2026, 3, 1, 9, 0).timestamp()
            ),
            has_recurrence=True,
        )
        wanted = MockEvent(
            identifier="evt-r",
            calendar=cal,
            occurrence_date=MockNSDate(target.timestamp()),
            has_recurrence=True,
        )
        other_series = MockEvent(
            identifier="evt-x",
            calendar=cal,
            occurrence_date=MockNSDate(target.timestamp()),
        )
        store = make_store(events=[first, other_series, wanted])
        store.calendarItemWithIdentifier_.return_value = first
        svc, _, _ = _service_with_event(MockEvent(), store=store)

        with patch.dict("sys.modules", {"Foundation": MagicMock()}):
            result = svc._find_event_by_id(f"evt-r/{target.isoformat()}")

        assert result is wanted
        assert result is not first

    def test_unmatched_occurrence_raises(self):
        cal = MockCalendar("Work", "cal-w")
        series = MockEvent(
            identifier="evt-r",
            calendar=cal,
            occurrence_date=MockNSDate(
                datetime(2026, 3, 1, 9, 0).timestamp()
            ),
            has_recurrence=True,
        )
        store = make_store(events=[series])
        store.calendarItemWithIdentifier_.return_value = series
        svc, _, _ = _service_with_event(MockEvent(), store=store)

        with patch.dict("sys.modules", {"Foundation": MagicMock()}):
            with pytest.raises(ValueError, match="Occurrence .* not found"):
                svc._find_event_by_id("evt-r/2026-03-15T09:00:00")

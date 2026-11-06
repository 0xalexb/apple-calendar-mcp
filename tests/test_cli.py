from __future__ import annotations

import argparse
import asyncio
import inspect
import json
import subprocess
import sys
from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

from apple_calendar_mcp import cli, server
from apple_calendar_mcp.eventkit_service import EventKitService
from tests.conftest import (
    MockCalendar,
    MockEvent,
    MockGeoLocation,
    MockNSDate,
    MockStructuredLocation,
    make_ek_module,
    make_store,
)

TOOL_FOR_VERB = {
    "calendars": "list_calendars",
    "events": "get_events",
    "all-events": "get_all_events",
    "create-calendar": "create_calendar",
    "create": "create_event",
    "update": "update_event",
    "delete": "delete_event",
    "move": "move_event",
    "quick-add": "quick_add",
}

START = datetime(2026, 3, 1, 9, 0)
START_ISO = START.isoformat()
NEXT_DAY = datetime(2026, 3, 2, 9, 0)
PLUS_HOUR = datetime(2026, 3, 1, 10, 0)


@pytest.fixture()
def service():
    svc = MagicMock()
    with (
        patch("apple_calendar_mcp.cli.EventKitService", return_value=svc),
        patch("apple_calendar_mcp.server._get_service", return_value=svc),
    ):
        yield svc


@pytest.fixture()
def work():
    return MockCalendar("Work", "cal-w")


@pytest.fixture()
def event(work):
    return MockEvent(
        title="Standup",
        identifier="evt-1",
        calendar=work,
        start_date=MockNSDate(START.timestamp()),
        end_date=MockNSDate(PLUS_HOUR.timestamp()),
    )


def run(capsys, *argv: str) -> tuple[int, str, str]:
    code = cli.main(list(argv))
    captured = capsys.readouterr()
    return code, captured.out, captured.err


def run_ok(capsys, *argv: str):
    code, out, err = run(capsys, *argv)
    assert code == 0, err
    assert out.endswith("\n") and out.count("\n") == 1
    return json.loads(out)


def _subparsers(parser: argparse.ArgumentParser) -> dict[str, argparse.ArgumentParser]:
    for action in parser._actions:
        if isinstance(action, argparse._SubParsersAction):
            return dict(action.choices)
    return {}


def _file_flag_violations(parser: argparse.ArgumentParser) -> list[str]:
    found = []
    if parser.fromfile_prefix_chars is not None:
        found.append("fromfile_prefix_chars")
    for action in parser._actions:
        for option in action.option_strings:
            if any(word in option for word in ("file", "path", "from")):
                found.append(option)
        if isinstance(action.type, argparse.FileType):
            found.append(f"FileType on {action.dest}")
    for child in _subparsers(parser).values():
        found.extend(_file_flag_violations(child))
    return found


class TestJsonMatchesTools:
    def test_calendars(self, capsys, service, work, event):
        service.get_all_calendars.return_value = [work]
        service.get_all_events.return_value = [event]

        printed = run_ok(capsys, "calendars")
        service.get_all_calendars.assert_called_once_with()

        service.reset_mock()
        assert printed == server.list_calendars()
        assert printed[0]["upcoming_event_count"] == 1

    def test_events(self, capsys, service, event):
        service.get_events.return_value = [event]

        printed = run_ok(
            capsys, "events", "--start-date", START_ISO, "--calendar-name", "Work"
        )
        service.get_events.assert_called_once_with(
            "Work", START, NEXT_DAY, calendar_id=None
        )

        service.reset_mock()
        assert printed == server.get_events(START_ISO, calendar_name="Work")

    def test_events_by_calendar_id_only(self, capsys, service, event):
        service.get_events.return_value = [event]

        printed = run_ok(
            capsys,
            "events",
            "--start-date",
            START_ISO,
            "--end-date",
            "2026-03-05T00:00:00",
            "--calendar-id",
            "cal-w",
        )
        service.get_events.assert_called_once_with(
            None, START, datetime(2026, 3, 5), calendar_id="cal-w"
        )

        service.reset_mock()
        assert printed == server.get_events(
            START_ISO, end_date="2026-03-05T00:00:00", calendar_id="cal-w"
        )

    def test_all_events(self, capsys, service, event):
        service.get_all_events.return_value = [event]

        printed = run_ok(capsys, "all-events", "--start-date", START_ISO)
        service.get_all_events.assert_called_once_with(START, NEXT_DAY)

        service.reset_mock()
        assert printed == server.get_all_events(START_ISO)
        assert list(printed) == ["Work"]

    def test_create_calendar(self, capsys, service):
        service.create_calendar.return_value = MockCalendar("Errands")

        printed = run_ok(capsys, "create-calendar", "--name", "Errands")
        service.create_calendar.assert_called_once_with("Errands")

        service.reset_mock()
        assert printed == server.create_calendar("Errands")
        assert printed == {"name": "Errands", "created": True}

    def test_create_minimal(self, capsys, service, event):
        service.create_event.return_value = event

        printed = run_ok(
            capsys, "create", "--title", "Standup", "--start-date", START_ISO
        )
        service.create_event.assert_called_once_with(
            title="Standup",
            start_date=START,
            end_date=PLUS_HOUR,
            calendar_name=None,
            calendar_id=None,
            is_all_day=False,
            location=None,
            url=None,
            notes=None,
            recurrence=None,
            availability=None,
            time_zone=None,
            alarm_minutes_before=None,
        )

        service.reset_mock()
        assert printed == server.create_event("Standup", START_ISO)

    def test_create_with_every_flag(self, capsys, service, event):
        service.create_event.return_value = event
        recurrence = {"frequency": "weekly", "interval": 2, "count": 5}

        printed = run_ok(
            capsys,
            "create",
            "--title",
            "Standup",
            "--start-date",
            START_ISO,
            "--end-date",
            "2026-03-01T09:30:00",
            "--calendar-name",
            "Work",
            "--calendar-id",
            "cal-w",
            "--is-all-day",
            "--location",
            "Room 4",
            "--url",
            "https://example.com/m",
            "--notes=-dial in",
            "--recurrence",
            json.dumps(recurrence),
            "--availability",
            "free",
            "--time-zone",
            "Europe/Berlin",
            "--alarm-minutes-before",
            "[10,60]",
        )
        service.create_event.assert_called_once_with(
            title="Standup",
            start_date=START,
            end_date=datetime(2026, 3, 1, 9, 30),
            calendar_name="Work",
            calendar_id="cal-w",
            is_all_day=True,
            location="Room 4",
            url="https://example.com/m",
            notes="-dial in",
            recurrence=recurrence,
            availability="free",
            time_zone="Europe/Berlin",
            alarm_minutes_before=[10, 60],
        )

        service.reset_mock()
        assert printed == server.create_event(
            "Standup",
            START_ISO,
            end_date="2026-03-01T09:30:00",
            calendar_name="Work",
            calendar_id="cal-w",
            is_all_day=True,
            location="Room 4",
            url="https://example.com/m",
            notes="-dial in",
            recurrence=recurrence,
            availability="free",
            time_zone="Europe/Berlin",
            alarm_minutes_before=[10, 60],
        )

    def test_create_string_recurrence(self, capsys, service, event):
        service.create_event.return_value = event

        run_ok(
            capsys,
            "create",
            "--title",
            "t",
            "--start-date",
            START_ISO,
            "--recurrence",
            "daily",
        )
        assert service.create_event.call_args.kwargs["recurrence"] == "daily"

    def test_create_no_is_all_day(self, capsys, service, event):
        service.create_event.return_value = event

        run_ok(
            capsys,
            "create",
            "--title",
            "t",
            "--start-date",
            START_ISO,
            "--no-is-all-day",
        )
        kwargs = service.create_event.call_args.kwargs
        assert kwargs["is_all_day"] is False
        assert kwargs["end_date"] == PLUS_HOUR

    def test_update(self, capsys, service, event):
        service.update_event.return_value = event

        printed = run_ok(
            capsys,
            "update",
            "--event-id",
            "evt-1",
            "--title",
            "Renamed",
            "--span",
            "future",
        )
        service.update_event.assert_called_once_with(
            "evt-1",
            title="Renamed",
            start_date=None,
            end_date=None,
            is_all_day=None,
            location=None,
            url=None,
            notes=None,
            availability=None,
            time_zone=None,
            alarm_minutes_before=None,
            recurrence=None,
            span="future",
        )

        service.reset_mock()
        assert printed == server.update_event("evt-1", title="Renamed", span="future")

    def test_update_clears_alarms_and_recurrence(self, capsys, service, event):
        service.update_event.return_value = event

        run_ok(
            capsys,
            "update",
            "--event-id",
            "evt-1",
            "--alarm-minutes-before",
            "[]",
            "--recurrence",
            "",
        )
        kwargs = service.update_event.call_args.kwargs
        assert kwargs["alarm_minutes_before"] == []
        assert kwargs["recurrence"] == ""

    def test_update_is_all_day_unset_true_false(self, capsys, service, event):
        service.update_event.return_value = event

        for flags, expected in (
            ([], None),
            (["--is-all-day"], True),
            (["--no-is-all-day"], False),
        ):
            service.update_event.reset_mock()
            run_ok(capsys, "update", "--event-id", "evt-1", *flags)
            assert service.update_event.call_args.kwargs["is_all_day"] is expected

    def test_delete(self, capsys, service):
        printed = run_ok(capsys, "delete", "--event-id", "evt-1")
        service.delete_event.assert_called_once_with("evt-1", span="this")

        service.reset_mock()
        assert printed == server.delete_event("evt-1")
        assert printed == {"id": "evt-1", "deleted": True}

    def test_delete_future(self, capsys, service):
        printed = run_ok(
            capsys, "delete", "--event-id", "evt-1/2026-03-01", "--span", "future"
        )
        service.delete_event.assert_called_once_with("evt-1/2026-03-01", span="future")

        service.reset_mock()
        assert printed == server.delete_event("evt-1/2026-03-01", span="future")

    def test_move(self, capsys, service, event):
        service.move_event.return_value = event

        printed = run_ok(
            capsys,
            "move",
            "--event-id",
            "evt-1",
            "--target-calendar-name",
            "Home",
            "--target-calendar-id",
            "cal-h",
        )
        service.move_event.assert_called_once_with(
            "evt-1", "Home", target_calendar_id="cal-h"
        )

        service.reset_mock()
        assert printed == server.move_event(
            "evt-1", target_calendar_name="Home", target_calendar_id="cal-h"
        )

    def test_quick_add(self, capsys, service, event):
        service.create_event.return_value = event

        printed = run_ok(
            capsys,
            "quick-add",
            "--title",
            "Call",
            "--start-date",
            START_ISO,
            "--notes",
            "ring back",
        )
        service.create_event.assert_called_once_with(
            title="Call", start_date=START, end_date=PLUS_HOUR, notes="ring back"
        )

        service.reset_mock()
        assert printed == server.quick_add("Call", START_ISO, notes="ring back")

    def test_empty_results_print_a_value(self, capsys, service):
        service.get_all_calendars.return_value = []
        service.get_all_events.return_value = []
        service.get_events.return_value = []

        assert run_ok(capsys, "calendars") == []
        assert run_ok(capsys, "events", "--start-date", START_ISO) == []
        assert run_ok(capsys, "all-events", "--start-date", START_ISO) == {}

    def test_non_ascii_is_not_escaped(self, capsys, service):
        service.create_calendar.return_value = MockCalendar("Café")

        code, out, _ = run(capsys, "create-calendar", "--name", "Café")
        assert code == 0
        assert out == '{"name": "Café", "created": true}\n'


class TestGeoLocation:
    @pytest.fixture()
    def geo_event(self, work):
        return MockEvent(
            title="Offsite",
            identifier="evt-g",
            calendar=work,
            start_date=MockNSDate(START.timestamp()),
            end_date=MockNSDate(PLUS_HOUR.timestamp()),
            structured_location=MockStructuredLocation(
                title="HQ", geo_location=MockGeoLocation(52.5, 13.4), radius=100.0
            ),
        )

    def test_events_with_a_geo_location(self, capsys, service, work, geo_event):
        service.get_events.return_value = [geo_event]
        out = run_ok(capsys, "events", "--start-date", START_ISO, "--calendar-name", "Work")
        assert out[0]["geo"] == {
            "title": "HQ",
            "latitude": 52.5,
            "longitude": 13.4,
            "radius": 100.0,
        }

    def test_update_prints_an_event_with_a_geo_location(self, capsys, service, geo_event):
        service.update_event.return_value = geo_event
        out = run_ok(capsys, "update", "--event-id", "evt-g", "--title", "Offsite")
        assert out["geo"]["latitude"] == 52.5


class TestExitCodes:
    @pytest.mark.parametrize(
        "argv",
        [
            ["events"],
            ["events", "--start", START_ISO],
            ["events", "--start-date", START_ISO, "--bogus", "x"],
            ["frobnicate"],
            [],
        ],
    )
    def test_usage_error_exits_1(self, capsys, service, argv):
        with pytest.raises(SystemExit) as exc:
            cli.main(argv)
        assert exc.value.code == 1
        captured = capsys.readouterr()
        assert captured.out == ""
        assert captured.err

    @pytest.mark.parametrize(
        "argv",
        [
            ["events", "--start-date", "not-a-date"],
            ["create", "--title", "t", "--start-date", START_ISO, "--alarm-minutes-before", "10"],
            ["create", "--title", "t", "--start-date", START_ISO, "--alarm-minutes-before", '["a"]'],
            ["create", "--title", "t", "--start-date", START_ISO, "--alarm-minutes-before", "[true]"],
            ["create", "--title", "t", "--start-date", START_ISO, "--alarm-minutes-before", "[1,"],
            ["create", "--title", "t", "--start-date", START_ISO, "--recurrence", "{bad"],
            ["create", "--title", "t", "--start-date", START_ISO, "--recurrence", "{}x"],
        ],
    )
    def test_bad_input_returns_1(self, capsys, service, argv):
        code, out, err = run(capsys, *argv)
        assert code == 1
        assert out == ""
        assert err.startswith("apple-calendar: ")

    def test_not_found_returns_1(self, capsys, service):
        service.delete_event.side_effect = ValueError("Event 'x' not found")

        code, out, err = run(capsys, "delete", "--event-id", "x")
        assert (code, out) == (1, "")
        assert "Event 'x' not found" in err

    def test_failed_save_returns_1(self, capsys, service):
        service.create_calendar.side_effect = RuntimeError("Failed to save")

        code, out, err = run(capsys, "create-calendar", "--name", "n")
        assert (code, out) == (1, "")
        assert "Failed to save" in err

    @pytest.mark.parametrize("exc", [PermissionError("denied"), TimeoutError("timed out")])
    def test_access_failure_at_startup_returns_2(self, capsys, exc):
        with patch("apple_calendar_mcp.cli.EventKitService", side_effect=exc):
            code, out, err = run(capsys, "calendars")
        assert (code, out) == (2, "")
        assert str(exc) in err

    def test_timeout_in_a_service_call_returns_2(self, capsys, service):
        service.get_all_calendars.side_effect = TimeoutError("timed out")

        code, out, err = run(capsys, "calendars")
        assert (code, out) == (2, "")
        assert "timed out" in err

    def test_error_leaves_stdout_empty(self, capsys, service):
        cal = MagicMock()
        cal.title.return_value = object()
        service.create_calendar.return_value = cal

        with pytest.raises(TypeError):
            cli.main(["create-calendar", "--name", "n"])
        assert capsys.readouterr().out == ""


class TestRecurrenceRejected:
    @pytest.fixture()
    def real(self, work):
        existing = MockEvent(
            title="Old",
            identifier="evt-1",
            calendar=work,
            start_date=MockNSDate(START.timestamp()),
            end_date=MockNSDate(PLUS_HOUR.timestamp()),
            recurrence_rules=[object()],
        )
        store = make_store(calendars=[work])
        store.calendarItemWithIdentifier_.return_value = existing
        ek = make_ek_module()
        ek.EKEvent.eventWithEventStore_.return_value = MockEvent(calendar=work)
        svc = EventKitService(event_store=store, ek_module=ek)
        with (
            patch("apple_calendar_mcp.cli.EventKitService", return_value=svc),
            patch.dict("sys.modules", {"Foundation": MagicMock()}),
        ):
            yield store

    @pytest.mark.parametrize("verb", ["create", "update"])
    @pytest.mark.parametrize(
        "recurrence,named",
        [
            ("{}", None),
            ('{"end":{"date":"2026-12-31T00:00:00"}}', "'end'"),
            ('{"frequency":"daily","days_of_month":[1]}', "'days_of_month'"),
        ],
    )
    def test_rejected_with_exit_1(self, capsys, real, verb, recurrence, named):
        if verb == "create":
            argv = ["create", "--title", "T", "--start-date", START_ISO]
        else:
            argv = ["update", "--event-id", "evt-1"]
        code, out, err = run(capsys, *argv, "--recurrence", recurrence)
        assert code == 1
        assert out == ""
        assert err.startswith("apple-calendar: ")
        if named:
            assert named in err
        real.saveEvent_span_commit_error_.assert_not_called()

    def test_update_empty_string_still_clears(self, capsys, real):
        run_ok(capsys, "update", "--event-id", "evt-1", "--recurrence", "")
        real.saveEvent_span_commit_error_.assert_called_once()

    def test_create_empty_string_makes_a_non_recurring_event(self, capsys, real):
        run_ok(capsys, "create", "--title", "T", "--start-date", START_ISO, "--recurrence", "")
        real.saveEvent_span_commit_error_.assert_called_once()


class TestNoFileFlag:
    def test_no_verb_has_a_file_flag(self):
        parser = cli._build_parser()

        assert set(_subparsers(parser)) == set(TOOL_FOR_VERB)
        assert _file_flag_violations(parser) == []

    @pytest.mark.filterwarnings("ignore::PendingDeprecationWarning")
    def test_file_flag_check_detects_a_file_flag(self):
        named = argparse.ArgumentParser()
        named.add_argument("--body-file")
        typed = argparse.ArgumentParser()
        typed.add_argument("--body", type=argparse.FileType("r"))
        prefixed = argparse.ArgumentParser(fromfile_prefix_chars="@")

        assert _file_flag_violations(named) == ["--body-file"]
        assert _file_flag_violations(typed) == ["FileType on body"]
        assert _file_flag_violations(prefixed) == ["fromfile_prefix_chars"]


class TestSurface:
    def test_flags_match_tool_parameters(self):
        verbs = _subparsers(cli._build_parser())

        for verb, tool_name in TOOL_FOR_VERB.items():
            params = set(inspect.signature(getattr(server, tool_name)).parameters)
            actions = [
                a for a in verbs[verb]._actions if not isinstance(a, argparse._HelpAction)
            ]
            assert {a.dest for a in actions} == params, verb
            for action in actions:
                flag = "--" + action.dest.replace("_", "-")
                if isinstance(action, argparse.BooleanOptionalAction):
                    assert action.option_strings == [flag, "--no-" + flag[2:]], verb
                else:
                    assert action.option_strings == [flag], verb

    def test_every_tool_has_a_verb(self):
        registered = {tool.name for tool in asyncio.run(server.mcp.list_tools())}

        assert registered - {"ping"} == set(TOOL_FOR_VERB.values())
        assert len(set(TOOL_FOR_VERB.values())) == len(TOOL_FOR_VERB)

    def test_abbreviated_flag_is_not_accepted(self):
        with pytest.raises(SystemExit) as exc:
            cli.main(["delete", "--event", "evt-1"])
        assert exc.value.code == 1


ISOLATION_SCRIPT = """
import sys
{extra}
import apple_calendar_mcp.cli
loaded = [m for m in ("apple_calendar_mcp.server", "mcp") if m in sys.modules]
sys.exit(1 if loaded else 0)
"""


def _import_check(extra: str) -> int:
    script = ISOLATION_SCRIPT.format(extra=extra)
    return subprocess.run([sys.executable, "-c", script], check=False).returncode


class TestIsolation:
    def test_cli_does_not_import_server(self):
        assert _import_check("") == 0

    def test_isolation_check_detects_server_import(self):
        assert _import_check("import apple_calendar_mcp.server") != 0

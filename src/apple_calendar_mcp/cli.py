from __future__ import annotations

import argparse
import json
import sys

from apple_calendar_mcp import operations
from apple_calendar_mcp.eventkit_service import EventKitService

EXIT_OK = 0
EXIT_BAD_INPUT = 1
EXIT_NO_ACCESS = 2

_OPERATIONS = {
    "calendars": operations.list_calendars,
    "events": operations.get_events,
    "all-events": operations.get_all_events,
    "create-calendar": operations.create_calendar,
    "create": operations.create_event,
    "update": operations.update_event,
    "delete": operations.delete_event,
    "move": operations.move_event,
    "quick-add": operations.quick_add,
}


class _Parser(argparse.ArgumentParser):
    def __init__(self, *args, **kwargs) -> None:
        # Abbreviations would accept flags that are not tool parameters.
        kwargs.setdefault("allow_abbrev", False)
        super().__init__(*args, **kwargs)

    # argparse exits 2 on a usage error, which callers would read as "access denied".
    def error(self, message: str) -> None:
        self.print_usage(sys.stderr)
        print(f"{self.prog}: error: {message}", file=sys.stderr)
        sys.exit(EXIT_BAD_INPUT)


def _add_event_fields(parser: argparse.ArgumentParser, *, is_all_day_default) -> None:
    parser.add_argument("--end-date")
    parser.add_argument(
        "--is-all-day",
        action=argparse.BooleanOptionalAction,
        default=is_all_day_default,
    )
    parser.add_argument("--location")
    parser.add_argument("--url")
    parser.add_argument("--notes")
    parser.add_argument("--recurrence")
    parser.add_argument("--availability")
    parser.add_argument("--time-zone")
    parser.add_argument("--alarm-minutes-before")


def _build_parser() -> argparse.ArgumentParser:
    parser = _Parser(
        prog="apple-calendar",
        description="Apple Calendar from the shell. JSON on stdout, errors on stderr.",
        epilog="Exit codes: 0 ok, 1 not found or bad input, 2 Calendar access denied or timed out.",
    )
    sub = parser.add_subparsers(dest="command", required=True, parser_class=_Parser)

    sub.add_parser("calendars", help="list calendars with their upcoming event count")

    events = sub.add_parser("events", help="events of one calendar in a date range")
    events.add_argument("--start-date", required=True)
    events.add_argument("--calendar-name")
    events.add_argument("--end-date")
    events.add_argument("--calendar-id")

    all_events = sub.add_parser("all-events", help="events of every calendar, grouped by calendar")
    all_events.add_argument("--start-date", required=True)
    all_events.add_argument("--end-date")

    create_calendar = sub.add_parser("create-calendar", help="create a calendar")
    create_calendar.add_argument("--name", required=True)

    create = sub.add_parser("create", help="create an event")
    create.add_argument("--title", required=True)
    create.add_argument("--start-date", required=True)
    create.add_argument("--calendar-name")
    create.add_argument("--calendar-id")
    _add_event_fields(create, is_all_day_default=False)

    update = sub.add_parser("update", help="change an event; only the given fields change")
    update.add_argument("--event-id", required=True)
    update.add_argument("--title")
    update.add_argument("--start-date")
    _add_event_fields(update, is_all_day_default=None)
    update.add_argument("--span", default="this")

    delete = sub.add_parser("delete", help="delete an event")
    delete.add_argument("--event-id", required=True)
    delete.add_argument("--span", default="this")

    move = sub.add_parser("move", help="move an event to another calendar")
    move.add_argument("--event-id", required=True)
    move.add_argument("--target-calendar-name")
    move.add_argument("--target-calendar-id")

    quick_add = sub.add_parser("quick-add", help="create an event in the default calendar")
    quick_add.add_argument("--title", required=True)
    quick_add.add_argument("--start-date", required=True)
    quick_add.add_argument("--notes")
    return parser


def _parse_alarm_minutes(raw: str | None) -> list[int] | None:
    if raw is None:
        return None
    try:
        value = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(f"--alarm-minutes-before is not valid JSON: {exc}") from exc
    if not isinstance(value, list) or any(type(item) is not int for item in value):
        raise ValueError("--alarm-minutes-before must be a JSON list of integers")
    return value


def _parse_recurrence(raw: str | None) -> str | dict | None:
    if raw is None or not raw.startswith("{"):
        return raw
    try:
        value = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(f"--recurrence is not valid JSON: {exc}") from exc
    if not isinstance(value, dict):
        raise ValueError("--recurrence must be a frequency string or a JSON object")
    return value


def _run(args: argparse.Namespace) -> object:
    params = {key: value for key, value in vars(args).items() if key != "command"}
    if "alarm_minutes_before" in params:
        params["alarm_minutes_before"] = _parse_alarm_minutes(params["alarm_minutes_before"])
    if "recurrence" in params:
        params["recurrence"] = _parse_recurrence(params["recurrence"])
    return _OPERATIONS[args.command](EventKitService(), **params)


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    try:
        result = _run(args)
    except (PermissionError, TimeoutError) as exc:
        print(f"apple-calendar: {exc}", file=sys.stderr)
        return EXIT_NO_ACCESS
    except (ValueError, RuntimeError) as exc:
        print(f"apple-calendar: {exc}", file=sys.stderr)
        return EXIT_BAD_INPUT
    out = json.dumps(result, ensure_ascii=False) + "\n"
    sys.stdout.write(out)
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())

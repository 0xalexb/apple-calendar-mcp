# EventKit Field Coverage — Read, Write, and Occurrence Identity

## Overview

The MCP server exports 11 of an EKEvent's fields and 3 of an EKCalendar's. An audit against live
pyobjc introspection found a large set of public, documented EventKit properties that never reach
the client — most importantly `status` (a canceled meeting is indistinguishable from a live one),
`availability` (busy/free, the basis of any "am I free?" question), `attendees`, `alarms`, and the
actual recurrence rule behind today's bare `has_recurrence` boolean.

This plan closes the read gap, adds the write-side parameters for the properties EventKit actually
lets us set, and fixes a bug found during the audit: every occurrence of a recurring series shares
one `calendarItemIdentifier`, so `update_event`/`delete_event` on the 5th occurrence of a weekly
standup silently modifies the first.

Benefits: clients can reason about attendance and availability, see and set reminders, express
recurrence beyond "every 1 period, forever", and address a single occurrence of a series.

## Context (from discovery)

- **Files involved**: `src/apple_calendar_mcp/server.py` (formatters, tool signatures),
  `src/apple_calendar_mcp/eventkit_service.py` (EventKit calls), `tests/test_tools_read.py`,
  `tests/test_tools_write.py`, `tests/test_eventkit_service.py`, new `tests/conftest.py`,
  `README.md`.
- **Patterns found**: `server.py` never imports EventKit — formatters duck-type pyobjc objects,
  which is exactly what lets the tests mock everything. `_RECURRENCE_MAP = {"daily": 0, ...}` and
  `_SPAN_MAP` on `EventKitService` already establish hardcoded-int-literal enum maps as the house
  style. Optional-clear uses the `location or None` idiom.
- **Test fakes**: all three test files define their own `MockEvent` / `MockCalendar` /
  `MockNSDate` (+ `MockNSURL` in two of them). Prefix is `Mock`, not `Fake`.
- **Assertion styles differ**: `TestFormatEvent` asserts key-by-key and therefore tolerates new
  keys; `TestListCalendars` uses exact-dict equality at `tests/test_tools_read.py:248,249,266` and
  will break the moment `list_calendars` grows a field.
- **Dependencies**: `pyobjc-framework-EventKit`, already present. Tests need no macOS runtime.

## Development Approach

- **Testing approach**: Regular (code first, then tests) — the formatters are pure functions over
  duck-typed objects, so the shape is clearer once written.
- Complete each task fully before moving to the next.
- Make small, focused changes.
- **CRITICAL: every task MUST include new/updated tests** for code changes in that task
  - write unit tests for new functions/methods
  - write unit tests for modified functions/methods
  - add new test cases for new code paths
  - update existing test cases if behaviour changes
  - tests cover both success and error scenarios
- **CRITICAL: all tests must pass before starting the next task** — no exceptions.
- **CRITICAL: update this plan file when scope changes during implementation.**
- Run `uv run pytest` after each change.
- Maintain backward compatibility: no existing `_format_event` key is renamed or removed, existing
  event ids stay valid, and `recurrence="weekly"` keeps working.

## Testing Strategy

- **Unit tests**: required for every task (see Development Approach).
- **E2E tests**: this project has none — no UI, and EventKit is mocked. Do not stand up a real
  calendar store; `uv run pytest` is the whole gate.
- Tests mock EventKit and Foundation. `EventKitService` takes injected `event_store` and
  `ek_module`; server tools are tested by patching `_get_service()`.

## Progress Tracking

- Mark completed items with `[x]` immediately when done.
- Add newly discovered tasks with ➕ prefix.
- Document issues/blockers with ⚠️ prefix.
- Update the plan if implementation deviates from the original scope.

## Solution Overview

Three layers, in dependency order:

1. **Read** — ten int→name enum maps and four new formatters in `server.py`, feeding an expanded
   `_format_event` and a new `_format_calendar`.
2. **Write** — three new scalar parameters plus one structured `recurrence` object on
   `create_event`/`update_event`, backed by two new name→int maps on `EventKitService`.
3. **Identity** — a composite `"<series-id>/<occurrence-ISO>"` event id and an occurrence-aware
   `_find_event_by_id`.

Key decisions and rationale:

- **Enum maps live in `server.py` as hardcoded int literals, not imported from EventKit.**
  `server.py` importing EventKit would break every test that feeds it a duck-typed mock.
  `_RECURRENCE_MAP` already does exactly this.
- **Empty collections are omitted, not emitted as `[]`.** A solo event with no attendees, alarms,
  or recurrence grows by ~8 short scalars instead of a dozen empty containers, which matters when
  an LLM client reads 50 events in one response.
- **`recurrence` becomes one structured object rather than five flat parameters** (user's explicit
  choice), keeping `create_event` at 13 parameters instead of 17. It still accepts a bare string
  for backward compatibility.
- **Some fields are read-only on purpose.** `status`, `attendees`, and `structuredLocation` are
  exported but never settable — see Technical Details.

## Technical Details

### Verified EventKit surface

Every selector and constant below was verified against live pyobjc in the design session. To
re-derive rather than trust this file (values can change across macOS releases):

```bash
# enum constants
uv run python -c "import EventKit as EK; print(EK.EKEventStatusCanceled, EK.EKEventAvailabilityFree, EK.EKParticipantStatusDeclined, EK.EKCalendarTypeBirthday, EK.EKSourceTypeSubscribed, EK.EKAlarmProximityLeave, EK.EKSaturday)"
# expected: 3 1 3 4 4 2 7

# selector existence
uv run python -c "import EventKit as EK; print([(c.__name__, s, hasattr(c, s)) for c, s in [(EK.EKEvent,'setAvailability_'),(EK.EKEvent,'setTimeZone_'),(EK.EKEvent,'setAlarms_'),(EK.EKEvent,'occurrenceDate'),(EK.EKAlarm,'alarmWithRelativeOffset_'),(EK.EKRecurrenceEnd,'recurrenceEndWithOccurrenceCount_'),(EK.EKRecurrenceDayOfWeek,'dayOfWeek_')]])"
# expected: every tuple ends True
```

### Read-side enum maps (`server.py`, module level)

```python
_EVENT_STATUS = {0: "none", 1: "confirmed", 2: "tentative", 3: "canceled"}
_AVAILABILITY = {-1: "not_supported", 0: "busy", 1: "free", 2: "tentative", 3: "unavailable"}
_PARTICIPANT_STATUS = {0: "unknown", 1: "pending", 2: "accepted", 3: "declined",
                       4: "tentative", 5: "delegated", 6: "completed", 7: "in_process"}
_PARTICIPANT_ROLE = {0: "unknown", 1: "required", 2: "optional", 3: "chair", 4: "non_participant"}
_PARTICIPANT_TYPE = {0: "unknown", 1: "person", 2: "room", 3: "resource", 4: "group"}
_CALENDAR_TYPE = {0: "local", 1: "caldav", 2: "exchange", 3: "subscription", 4: "birthday"}
_SOURCE_TYPE = {0: "local", 1: "exchange", 2: "caldav", 3: "mobileme",
                4: "subscribed", 5: "birthdays"}
_ALARM_PROXIMITY = {0: "none", 1: "enter", 2: "leave"}
_FREQUENCY = {0: "daily", 1: "weekly", 2: "monthly", 3: "yearly"}
_WEEKDAY = {1: "sunday", 2: "monday", 3: "tuesday", 4: "wednesday",
            5: "thursday", 6: "friday", 7: "saturday"}
```

An unmapped int must fall back to the raw value rather than raise — EventKit can add cases.

### New formatters (`server.py`)

| Formatter | Output | Source selectors |
|---|---|---|
| `_format_participant(p)` | `{name, email, status, role, type, is_current_user}` | `name()`, `URL()` (a `mailto:` NSURL — `emailAddress` is a **private** selector, do not use), `participantStatus()`, `participantRole()`, `participantType()`, `isCurrentUser()` |
| `_format_alarm(a)` | `{relative_offset_minutes}` or `{absolute_date}`, plus `proximity` when non-`none` | `relativeOffset()` (seconds, negative = before), `absoluteDate()`, `proximity()` |
| `_format_recurrence_rule(r)` | `{frequency, interval, days_of_week?, days_of_month?, months_of_year?, week_positions?, end?}` | `frequency()`, `interval()`, `daysOfTheWeek()` (each an `EKRecurrenceDayOfWeek` with `dayOfTheWeek()` / `weekNumber()`), `daysOfTheMonth()`, `monthsOfTheYear()`, `setPositions()`, `recurrenceEnd()` → `{date}` from `endDate()` or `{occurrence_count}` from `occurrenceCount()` |
| `_format_calendar(cal)` | `{id, name, type, source, source_type, writable, immutable, subscribed, color}` | `calendarIdentifier()`, `title()`, `type()`, `source().title()`, `source().sourceType()`, `allowsContentModifications()`, `isImmutable()`, `isSubscribed()`, `color()` |

`_format_alarm` emits `relative_offset_minutes` as `relativeOffset() / 60` (so a 10-minute-early
alarm reads `-10`).

### `_format_event` final shape

Unchanged keys (all 11): `id`, `title`, `start_date`, `end_date`, `is_all_day`, `location`, `url`,
`notes`, `calendar`, `calendar_id`, `has_recurrence`.

Always-present additions: `status`, `availability`, `time_zone` (`event.timeZone()` → `.name()`),
`is_detached`, `occurrence_date`, `created_at` (`creationDate`), `last_modified`
(`lastModifiedDate`), `external_id` (`calendarItemExternalIdentifier`), `series_id`.

Omitted-when-empty additions: `organizer`, `attendees`, `alarms`, `recurrence_rules`, `geo` (from
`structuredLocation()` when it carries coordinates).

Not exported, deliberately: `birthdayContactIdentifier`, `UUID` (deprecated), and the
`hasNotes`/`hasAttendees`/`hasAlarms` booleans (redundant once the arrays exist).

### Write-side maps (`EventKitService` class attributes)

```python
_AVAILABILITY_MAP = {"busy": 0, "free": 1, "tentative": 2, "unavailable": 3}
_WEEKDAY_MAP = {"sunday": 1, "monday": 2, "tuesday": 3, "wednesday": 4,
                "thursday": 5, "friday": 6, "saturday": 7}
```

### New write parameters

`create_event` and `update_event` both gain:

- `availability: str | None` → `_AVAILABILITY_MAP` → `setAvailability_`
- `time_zone: str | None` — IANA name → `Foundation.NSTimeZone.timeZoneWithName_` →
  `setTimeZone_`; a name NSTimeZone rejects (returns `None`) raises `ValueError`
- `alarm_minutes_before: list[int] | None` → `EKAlarm.alarmWithRelativeOffset_(-m * 60)` for each,
  then `setAlarms_`

`recurrence` changes from `str | None` to `str | dict | None`:

```python
recurrence = {
    "frequency": "weekly",                    # required
    "interval": 2,                            # optional, default 1
    "days_of_week": ["monday", "thursday"],   # optional
    "end_date": "2026-12-31",                 # optional, ISO; xor count
    "count": 10,                              # optional; xor end_date
}
```

A plain string normalizes to `{"frequency": <string>}`, so every current caller, test, and README
example keeps working unchanged.

`_create_recurrence_rule` switches to the full selector
`initRecurrenceWithFrequency_interval_daysOfTheWeek_daysOfTheMonth_monthsOfTheYear_weeksOfTheYear_daysOfTheYear_setPositions_end_`,
passing `None` for the axes we don't expose. Recurrence end comes from
`EKRecurrenceEnd.recurrenceEndWithEndDate_` or `.recurrenceEndWithOccurrenceCount_`; weekdays from
`EKRecurrenceDayOfWeek.dayOfWeek_`.

**Clearing** follows the existing `location or None` idiom: `alarm_minutes_before=[]` strips
alarms, `recurrence=""` strips recurrence rules, `None` means "leave alone".

**Deliberately not writable** — do not implement setters for these:

- `status` — no public `setStatus_`.
- `attendees` — `setAttendees_` exists but is a private selector; the public API is read-only.
- `geo` / `structuredLocation` — real coordinates need CoreLocation, and `locationWithTitle_` adds
  nothing over the plain `location` string.

### Occurrence identity

All occurrences of a recurring series share one `calendarItemIdentifier`, and
`calendarItemWithIdentifier_` returns the first occurrence. Today's `id` is therefore ambiguous.

- `id` stays the bare `calendarItemIdentifier()` for events with no recurrence rules, so existing
  ids remain valid.
- For a recurring event, `id` becomes `"<calendarItemIdentifier>/<occurrenceDate ISO>"`.
- `series_id` always carries the bare identifier, so a client can address the whole series.
- Separator is the **first** `/`: `calendarItemIdentifier` is an Apple-generated UUID, and ISO
  timestamps contain `:` but never `/`.

`_find_event_by_id` resolution:

1. No `/` → `calendarItemWithIdentifier_`, exactly as today.
2. With `/` → resolve the series by identifier to get its calendar, build
   `predicateForEventsWithStartDate_endDate_calendars_` over occurrence_date ± 1 day scoped to
   that one calendar, and select the event whose `calendarItemIdentifier()` matches **and** whose
   `occurrenceDate()` is within 1 second of the target.
3. No match → `ValueError("Occurrence '<id>' not found")`, matching the existing not-found style.

`update_event` gains `span: str = "this"` using the existing `_SPAN_MAP`, so that now occurrences
are addressable a series-wide edit is expressible too. `delete_event` already has `span`.

## What Goes Where

- **Implementation Steps**: code, tests, README — everything achievable in this repo.
- **Post-Completion**: verification against a real calendar on macOS, which no unit test covers.

## Implementation Steps

### Task 1: Extract shared test fakes into conftest.py

**Files:**
- Create: `tests/conftest.py`
- Modify: `tests/test_tools_read.py`
- Modify: `tests/test_tools_write.py`
- Modify: `tests/test_eventkit_service.py`

- [x] create `tests/conftest.py` with `MockCalendar`, `MockSource`, `MockNSDate`, `MockNSURL`,
      `MockEvent`, `MockParticipant`, `MockAlarm`, `MockRecurrenceRule`, `MockRecurrenceEnd`,
      `MockDayOfWeek`, `MockTimeZone` — keeping the existing `Mock` prefix, not `Fake`
- [x] give `MockEvent` a default for every selector `_format_event` will call, so a fake built with
      no arguments still formats cleanly
- [x] delete the three duplicated per-file fake definitions and import from `conftest` instead
      ⚠️ `MockCalendar._counter` is class state shared across tests; keep the auto-increment
      behaviour when merging the three variants or ids will collide
- [x] verify no test file still defines its own `MockEvent`:
      `grep -c "^class MockEvent" tests/test_*.py` must print `0` for all three
- [x] run `uv run pytest` — must pass with the same test count as before this task

### Task 2: Add enum maps and the participant, alarm, and recurrence formatters

**Files:**
- Modify: `src/apple_calendar_mcp/server.py`
- Modify: `tests/test_tools_read.py`

- [x] add the ten `_EVENT_STATUS` … `_WEEKDAY` module-level maps from Technical Details
- [x] add `_format_participant`, `_format_alarm`, `_format_recurrence_rule`, each returning the
      documented shape and falling back to the raw int for an unmapped enum value
- [x] `_format_alarm` converts `relativeOffset()` seconds to `relative_offset_minutes`, and omits
      `proximity` when it maps to `"none"`
- [x] `_format_recurrence_rule` omits every optional axis that is nil or empty, and renders
      `recurrenceEnd()` as `{"date": ...}` or `{"occurrence_count": ...}`
- [x] write tests covering each enum map's full domain, both alarm variants, and a recurrence rule
      with and without days/end
- [x] write tests for the unmapped-enum fallback and for a nil `recurrenceEnd`
- [x] run tests — must pass before Task 3

### Task 3: Expand _format_event with the new fields

**Files:**
- Modify: `src/apple_calendar_mcp/server.py`
- Modify: `tests/test_tools_read.py`

- [x] add the always-present scalars: `status`, `availability`, `time_zone`, `is_detached`,
      `occurrence_date`, `created_at`, `last_modified`, `external_id`, `series_id`
- [x] add `organizer`, `attendees`, `alarms`, `recurrence_rules`, `geo`, each omitted from the dict
      entirely when nil or empty
- [x] keep all 11 existing keys byte-identical, `has_recurrence` included
      ⚠️ `_format_event` currently calls `event.calendar()` twice; resolve it once into a local
- [x] write a test asserting a fully-populated event produces every key
- [x] write a test asserting a minimal event's dict contains none of the five optional keys —
      `assert set(result) & {"organizer", "attendees", "alarms", "recurrence_rules", "geo"} == set()`
- [x] run tests — must pass before Task 4

### Task 4: Expand list_calendars via _format_calendar

**Files:**
- Modify: `src/apple_calendar_mcp/server.py`
- Modify: `tests/test_tools_read.py`

- [x] add `_format_calendar` returning `{id, name, type, source, source_type, writable, immutable,
      subscribed, color}`
- [x] rewrite `list_calendars` to spread `_format_calendar(cal)` and add `upcoming_event_count`
- [x] handle `cal.source()` returning nil — `source` and `source_type` become `None`, not a crash
- [x] update the three exact-dict-equality assertions at `tests/test_tools_read.py:248,249,266` by
      extending the expected dicts with the new keys; keep them exact-equality, do not weaken them
      to subset checks and do not delete any test
- [x] write tests for a read-only calendar (`writable is False`) and a subscribed calendar
- [x] run tests — must pass before Task 5

### Task 5: Add availability, time_zone, and alarms to EventKitService

**Files:**
- Modify: `src/apple_calendar_mcp/eventkit_service.py`
- Modify: `tests/test_eventkit_service.py`

- [x] add `_AVAILABILITY_MAP` and `_WEEKDAY_MAP` class attributes beside `_RECURRENCE_MAP`
- [x] add `availability`, `time_zone`, `alarm_minutes_before` parameters to `create_event` and
      `update_event`, applying `setAvailability_`, `setTimeZone_`, `setAlarms_`
- [x] add a `_make_nstimezone` helper mirroring `_make_nsurl`, raising
      `ValueError(f"Invalid time zone: {name}")` when `timeZoneWithName_` returns `None`
- [x] make `alarm_minutes_before=[]` clear alarms while `None` leaves them untouched, matching the
      existing `location or None` idiom
- [x] write tests asserting the offset conversion: 10 minutes must call
      `alarmWithRelativeOffset_` with `-600`
- [x] write tests for invalid availability and invalid time zone both raising `ValueError`
- [x] run tests — must pass before Task 6

### Task 6: Replace the recurrence string with a structured object

**Files:**
- Modify: `src/apple_calendar_mcp/eventkit_service.py`
- Modify: `tests/test_eventkit_service.py`

- [x] add a `_normalize_recurrence` helper turning `"weekly"` into `{"frequency": "weekly"}` and
      passing a dict through, so existing callers are unaffected
- [x] rewrite `_create_recurrence_rule` to use the full
      `initRecurrenceWithFrequency_interval_daysOfTheWeek_..._end_` selector, passing `None` for
      unexposed axes
- [x] build `recurrenceEnd` from `end_date` or `count`, raising `ValueError` when both are given
- [x] map `days_of_week` names through `_WEEKDAY_MAP` into `EKRecurrenceDayOfWeek.dayOfWeek_`,
      raising `ValueError` on an unknown weekday name
- [x] add recurrence handling to `update_event`, where `recurrence=""` clears the rules
- [x] write a test asserting `recurrence="weekly"` produces frequency `1`, interval `1`, and `None`
      for every other argument — proving no behaviour change for existing callers
- [x] write tests for interval, days_of_week, end_date, count, and the both-set `ValueError`
- [x] run tests — must pass before Task 7

### Task 7: Surface the new write parameters on the MCP tools

**Files:**
- Modify: `src/apple_calendar_mcp/server.py`
- Modify: `tests/test_tools_write.py`

- [x] add `availability`, `time_zone`, `alarm_minutes_before` and the widened `recurrence` to the
      `create_event` and `update_event` tool signatures
- [x] update both docstrings — they are the tool descriptions the model reads, so spell out the
      `recurrence` object's keys and the `end_date`/`count` exclusivity
- [x] verify `create_event` has 13 parameters, not 17:
      `uv run python -c "import inspect; from apple_calendar_mcp import server; print(len(inspect.signature(server.create_event.fn).parameters))"`
      ⚠️ if `MCPServer.tool()` does not expose the wrapped function as `.fn`, read the attribute the
      decorator actually sets rather than changing the assertion to something weaker
- [x] write tests asserting each new parameter reaches `EventKitService` with the right value
- [x] write tests for `recurrence` passed as a string and as a dict through the tool layer
- [x] run tests — must pass before Task 8

### Task 8: Make event ids occurrence-aware

**Files:**
- Modify: `src/apple_calendar_mcp/server.py`
- Modify: `src/apple_calendar_mcp/eventkit_service.py`
- Modify: `tests/test_tools_read.py`
- Modify: `tests/test_eventkit_service.py`

- [x] in `_format_event`, emit the composite `"<identifier>/<occurrence ISO>"` id only when the
      event has recurrence rules and a non-nil `occurrenceDate()`; always emit bare `series_id`
- [x] split on the first `/` in `_find_event_by_id`, keeping the bare-identifier path byte-identical
      to today's behaviour
- [x] for the composite path, resolve the series, then run
      `predicateForEventsWithStartDate_endDate_calendars_` over occurrence_date ± 1 day scoped to
      the series' calendar and match on identifier plus `occurrenceDate()` within 1 second
      ⚠️ the predicate is inclusive of overlapping events, so the identifier check is what makes
      the match exact — do not rely on the window alone
- [x] raise `ValueError(f"Occurrence '{event_id}' not found")` when nothing matches
- [x] write a round-trip test: format a recurring occurrence, feed its `id` back to
      `_find_event_by_id`, and assert the returned object is the same occurrence — not the first
- [x] write tests for a non-recurring id (unchanged path) and for the occurrence-not-found error
- [x] run tests — must pass before Task 9

### Task 9: Add span to update_event

**Files:**
- Modify: `src/apple_calendar_mcp/eventkit_service.py`
- Modify: `src/apple_calendar_mcp/server.py`
- Modify: `tests/test_eventkit_service.py`
- Modify: `tests/test_tools_write.py`

- [x] add `span: str = "this"` to `EventKitService.update_event`, resolved through `_SPAN_MAP` and
      passed to `saveEvent_span_commit_error_` in place of the hardcoded `0`
- [x] add the same parameter to the `update_event` tool, documenting it the way `delete_event`
      already documents its own
- [x] raise `ValueError` on an invalid span, matching `delete_event`'s existing message
- [x] write a test asserting `span="future"` reaches `saveEvent_span_commit_error_` as `1`
- [x] write a test asserting the default still passes `0`
- [x] run tests — must pass before Task 10

### Task 10: Verify acceptance criteria

- [x] verify every field listed in Technical Details appears in `_format_event` or
      `_format_calendar` output, and that nothing in the "not exported" list does
- [x] verify the read-only trio has no setter: `grep -c "setStatus_\|setAttendees_\|setStructuredLocation_" src/apple_calendar_mcp/eventkit_service.py` must print `0`
- [x] verify `server.py` still does not import EventKit:
      `grep -c "^import EventKit\|^from EventKit" src/apple_calendar_mcp/server.py` must print `0`
- [x] re-run the two re-derivation commands in Technical Details and confirm the expected output
- [x] run the full suite: `uv run pytest` — all tests pass, count is strictly greater than the
      pre-change count
- [x] verify the server still starts:
      `echo '{"jsonrpc":"2.0","id":0,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"test","version":"1.0"}}}' | uv run apple-calendar-mcp`
      returns a JSON-RPC result, not a traceback

### Task 11: [Final] Update documentation

- [x] document the `_format_event` and `list_calendars` field sets in `README.md`, including which
      keys are omitted when empty
- [x] document the `recurrence` object shape and note that the plain string still works
- [x] note in `README.md` that ids of recurring events are composite, and what `series_id` is for
- [x] add to `CLAUDE.md`: the "`server.py` must not import EventKit" constraint and the composite
      id format, both non-obvious and easy to break
- [x] move this plan to `docs/plans/completed/`

## Post-Completion

*Items requiring manual intervention or external systems — no checkboxes, informational only*

**Manual verification** (nothing below is covered by the mocked test suite):

- Run against a real calendar on macOS and confirm `attendees`, `organizer`, and `status` populate
  on an actual invitation — the shape of a real `EKParticipant` is only assumed here.
- Confirm `availability` round-trips on an Exchange calendar; `supportedEventAvailabilities` varies
  by calendar type, and EventKit may silently coerce an unsupported value.
- Edit and delete a single occurrence of a real recurring series, then confirm in Calendar.app that
  the other occurrences are untouched. This is the bug the plan fixes and mocks cannot prove it.
- Check the response size of `get_all_events` over a busy week to confirm the omit-when-empty rule
  actually held the growth down.

**External system updates**:

- None. The server is not published to PyPI and has no consumers beyond the MCP clients that read
  the tool schema at connect time, which regenerates automatically.

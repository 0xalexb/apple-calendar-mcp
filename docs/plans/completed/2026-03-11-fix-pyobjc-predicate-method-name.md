# Fix incorrect PyObjC predicate method name

## Overview

Fix the wrong PyObjC method name `predicateForEventsWithStart_end_calendars_` (missing "Date" in two selector components) and update tests to assert the correct method name, preventing regression.

## Context

- Files involved: `src/apple_calendar_mcp/eventkit_service.py`, test files for eventkit_service
- Related patterns: All other PyObjC method names in the codebase are correct; this is the only instance
- Dependencies: None

## Development Approach

- **Testing approach**: Regular (code first, then tests)
- Complete each task fully before moving to the next
- **CRITICAL: every task MUST include new/updated tests**
- **CRITICAL: all tests must pass before starting next task**

## Implementation Steps

### Task 1: Fix the predicate method name

**Files:**
- Modify: `src/apple_calendar_mcp/eventkit_service.py`

- [x] Line 103: Replace `predicateForEventsWithStart_end_calendars_` with `predicateForEventsWithStartDate_endDate_calendars_`
- [x] Line 118: Replace `predicateForEventsWithStart_end_calendars_` with `predicateForEventsWithStartDate_endDate_calendars_`
- [x] Update tests: verify the mock store receives calls to `predicateForEventsWithStartDate_endDate_calendars_` (not the old name) in tests for `get_events` and `get_all_events`
- [x] Run project test suite - must pass before task 2

### Task 2: Verify acceptance criteria

- [x] Run full test suite (`uv run pytest`)
- [x] Run linter (`uv run ruff check src/ tests/`)
- [x] Move this plan to `docs/plans/completed/`

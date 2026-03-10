# Apple Calendar MCP Server

## Quick Reference

```bash
uv sync                          # Install deps
uv run pytest                    # Run tests
uv run ruff check src/ tests/    # Lint
uv run apple-calendar-mcp        # Run server
```

## Architecture

- **`server.py`** — FastMCP tool definitions, formatting helpers, service initialization
- **`eventkit_service.py`** — All EventKit (pyobjc) wrapper logic; isolates native calls to one file

## Conventions

- Python 3.11+, type hints via `from __future__ import annotations`
- Entity type: `EKEntityTypeEvent` (0)
- Dates: `NSDate` objects, ISO 8601 format at the tool API level
- Span values: `_SPAN_MAP = {"this": 0, "future": 1}` for save/delete operations
- Recurrence: `_RECURRENCE_MAP` → `EKRecurrenceFrequency` values (daily=0, weekly=1, monthly=2, yearly=3)
- Calendar fetching: synchronous `eventsMatchingPredicate:` (not async like reminders)

## Error Handling

- `ValueError` — invalid input (bad calendar name, event not found, invalid recurrence)
- `RuntimeError` — EventKit operation failed (save, delete)
- `TimeoutError` — permission request timeout

## Testing

- Tests mock EventKit and Foundation; no macOS-specific runtime needed
- `EventKitService` accepts injected `event_store` and `ek_module` for DI
- Server tools tested via patching `_get_service()`

# Apple Calendar MCP Server

## Quick Reference

```bash
uv sync                          # Install deps
uv run pytest                    # Run tests
uv run ruff check src/ tests/    # Lint
uv run apple-calendar-mcp        # Run server
```

## Architecture

- **`server.py`** — FastMCP tool wrappers (signatures and docstrings are the MCP surface), service initialization
- **`operations.py`** — one function per tool, `(service, **tool_params) -> result`; `server.py` and `cli.py` both call it, so the transports cannot drift
- **`formatting.py`** — enum maps and `_format_*` helpers
- **`cli.py`** — the `apple-calendar` console script; one verb per tool, JSON on stdout, exit `0`/`1`/`2`
- **`eventkit_service.py`** — All EventKit (pyobjc) wrapper logic; isolates native calls to one file

## Distribution

- **Not published to PyPI** — installed via GitHub releases
- Release workflow (`.github/workflows/release.yml`) generates a bash wrapper script
- Wrapper runs: `uvx --from "git+https://github.com/0xalexb/apple-calendar-mcp@v${VERSION}" apple-calendar-mcp`
- Homebrew tap: `0xalexb/homebrew-apps` — formula auto-updated by release workflow
- To debug startup: `echo '{"jsonrpc":"2.0","id":0,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"test","version":"1.0"}}}' | uv run apple-calendar-mcp`

## Conventions

- Python 3.11+, type hints via `from __future__ import annotations`
- Entity type: `EKEntityTypeEvent` (0)
- Dates: `NSDate` objects, ISO 8601 format at the tool API level
- Span values: `_SPAN_MAP = {"this": 0, "future": 1}` for save/delete operations
- Recurrence: `_RECURRENCE_MAP` → `EKRecurrenceFrequency` values (daily=0, weekly=1, monthly=2, yearly=3)
- Calendar fetching: synchronous `eventsMatchingPredicate:` (not async like reminders)
- `server.py`, `operations.py` and `formatting.py` must never import EventKit — the formatters
  duck-type pyobjc objects, which is what lets the tests run without a macOS runtime. Enum maps
  use hardcoded int literals
- `cli.py` and the modules it imports must never import `server` or `mcp`, so the short-lived CLI
  starts fast; `tests/test_cli.py` asserts it
- No CLI verb may have a file flag: deck checks the Apple backends by verb only and relies on it
- Event ids are composite for recurring events: `<calendarItemIdentifier>/<occurrence ISO>`. All
  occurrences share one `calendarItemIdentifier`, so `calendarItemWithIdentifier:` alone always
  returns the first occurrence
- Read-only in public EventKit, do not add setters: `status`, `attendees`, `structuredLocation`

## Error Handling

- `ValueError` — invalid input (bad calendar name, event not found, invalid recurrence)
- `RuntimeError` — EventKit operation failed (save, delete)
- `TimeoutError` — permission request timeout

## Testing

- Tests mock EventKit and Foundation; no macOS-specific runtime needed
- `EventKitService` accepts injected `event_store` and `ek_module` for DI
- Server tools tested via patching `_get_service()`

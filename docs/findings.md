# Fix: Incorrect PyObjC method name for event predicate

## Context

`list_calendars` (and any tool calling `get_events`/`get_all_events`) fails at runtime with:
```
'EKEventStore' object has no attribute 'predicateForEventsWithStart_end_calendars_'
```

The PyObjC method name is wrong — it's missing `Date` in two places.

## Change

**File:** `src/apple_calendar_mcp/eventkit_service.py` (lines 103, 118)

Replace:
```python
self._store.predicateForEventsWithStart_end_calendars_(
```
With:
```python
self._store.predicateForEventsWithStartDate_endDate_calendars_(
```

Both occurrences: in `get_events()` and `get_all_events()`.

No test changes needed — mocks use `MagicMock` which auto-creates attributes.

## Verification

```bash
echo '{"jsonrpc":"2.0","id":0,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"test","version":"1.0"}}}' | uv run apple-calendar-mcp
uv run pytest
```

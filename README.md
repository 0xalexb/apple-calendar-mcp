# Apple Calendar MCP Server

MCP server for Apple Calendar — lets Claude read, create, update, and manage calendar events through the native EventKit framework.

## Tools

| Tool | Description |
|------|-------------|
| `ping` | Health check |
| `list_calendars` | All calendars with upcoming event counts |
| `get_events` | Events for one calendar in a date range |
| `get_all_events` | All events grouped by calendar |
| `create_calendar` | Create a new calendar |
| `create_event` | Full event creation with optional recurrence |
| `update_event` | Partial update of an existing event |
| `delete_event` | Delete event (this occurrence or future) |
| `move_event` | Move event to another calendar |
| `quick_add` | Fast event creation in default calendar |

## Event fields

`get_events`, `get_all_events`, and the write tools all return the same event shape. These keys
are always present:

`id`, `series_id`, `title`, `start_date`, `end_date`, `is_all_day`, `location`, `url`, `notes`,
`calendar`, `calendar_id`, `has_recurrence`, `status` (none/confirmed/tentative/canceled),
`availability` (busy/free/tentative/unavailable), `time_zone`, `is_detached`, `occurrence_date`,
`created_at`, `last_modified`, `external_id`.

These are omitted entirely when the event has none, rather than returned empty:

`organizer`, `attendees`, `alarms`, `recurrence_rules`, `geo`.

`list_calendars` returns `id`, `name`, `type`, `source`, `source_type`, `writable`, `immutable`,
`subscribed`, `color`, and `upcoming_event_count`. Check `writable` before trying to create an
event in a calendar — subscribed and holiday calendars reject writes.

### Recurring event ids

An event with recurrence rules gets a composite `id` of `<series-id>/<occurrence ISO date>`, so
`update_event` and `delete_event` act on the occurrence you actually read. `series_id` always
holds the bare identifier if you want to address the whole series instead.

### Recurrence

`create_event` and `update_event` take `recurrence` as either a frequency string
(`"daily"`, `"weekly"`, `"monthly"`, `"yearly"`) or an object:

```json
{
  "frequency": "weekly",
  "interval": 2,
  "days_of_week": ["monday", "thursday"],
  "end_date": "2026-12-31",
  "count": 10
}
```

Only `frequency` is required. `end_date` and `count` are mutually exclusive. In `update_event`,
`recurrence: ""` removes the recurrence rules and `alarm_minutes_before: []` removes the alarms.

`status` and `attendees` are read-only — EventKit exposes no public API to set them.

## Install

### Homebrew (recommended)

```bash
brew install 0xalexb/apps/apple-calendar-mcp
```

### uvx (no local install)

```bash
uvx --from "git+https://github.com/0xalexb/apple-calendar-mcp" apple-calendar-mcp
```

### From source

```bash
git clone https://github.com/0xalexb/apple-calendar-mcp.git
cd apple-calendar-mcp
uv sync
```

## Configure

### Claude Code

```bash
claude mcp add apple-calendar-mcp apple-calendar-mcp
```

Or add to `~/.claude/settings.json`:

```json
{
  "mcpServers": {
    "apple-calendar-mcp": {
      "command": "apple-calendar-mcp"
    }
  }
}
```

### Claude Desktop

Add to `~/Library/Application Support/Claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "apple-calendar-mcp": {
      "command": "apple-calendar-mcp"
    }
  }
}
```

## Development

```bash
uv sync
uv run pytest
uv run ruff check src/ tests/
```

## Requirements

- macOS with Calendar access (EventKit)
- Python 3.11+

## Uninstall

```bash
# Homebrew
brew uninstall apple-calendar-mcp

# uvx
uv cache prune
```

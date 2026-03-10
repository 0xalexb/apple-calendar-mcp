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

## Install

### Homebrew (recommended)

```bash
brew install 0xalexb/apps/apple-calendar-mcp
```

### uvx (no local install)

```bash
uvx apple-calendar-mcp
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

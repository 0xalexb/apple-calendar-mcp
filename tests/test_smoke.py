def test_import_server():
    from apple_calendar_mcp import server

    assert hasattr(server, "mcp")
    assert hasattr(server, "main")


def test_ping_tool():
    from apple_calendar_mcp.server import ping

    assert ping() == "pong"


def test_recurrence_description_names_the_rules():
    import asyncio
    from pathlib import Path

    from apple_calendar_mcp import server

    tools = {tool.name: tool.description for tool in asyncio.run(server.mcp.list_tools())}
    readme = (Path(__file__).parent.parent / "README.md").read_text().replace("`", "")
    keys = ("frequency", "interval", "end_date", "count", "days_of_week")

    for name in ("create_event", "update_event"):
        assert "{} is an error" in tools[name]
    assert 'only "" clears' in tools["update_event"]
    for key in keys:
        assert key in tools["create_event"]
        assert key in readme
    for key in ("end", "days_of_month", "months_of_year", "week_positions"):
        assert key in tools["create_event"]
        assert key in readme
    assert "{} is an error" in readme
    assert 'only "" clears' in readme

import pytest
import logging

from apm_mcp.config import Settings
from apm_mcp.server import build_server
from apm_mcp import server as server_module
from conftest import FakeClient


@pytest.mark.asyncio
@pytest.mark.parametrize("transport", ["stdio", "sse"])
async def test_exactly_eleven_read_only_tools_are_registered_for_every_transport(transport):
    settings = Settings(api_url="https://apm.example", api_key="secret", mcp_transport=transport)
    server = build_server(settings, FakeClient({}))
    tools = await server.list_tools()
    assert {tool.name for tool in tools} == {"GetAlarms", "GetAlarmDetails", "GetAlarmNotes", "SearchMonitors",
        "ListMonitors", "GetMonitorSummary", "GetServerContext", "GetMonitorRelationships",
        "GetMonitorGroupTopology", "ListMonitorMetrics", "GetPerformanceMetrics"}
    assert "secret" not in str(tools)
    forbidden = ("apikey", "api_key", "password", "token", "authorization")
    assert not any(term in str([(tool.name, tool.inputSchema) for tool in tools]).lower() for term in forbidden)


def test_sse_network_settings_are_applied_to_fastmcp():
    settings = Settings(
        api_url="https://apm.example", api_key="secret", mcp_transport="sse",
        mcp_host="0.0.0.0", mcp_port=19090, mcp_sse_path="/events",
        mcp_message_path="/inbox/",
    )
    server = build_server(settings, FakeClient({}))
    assert server.settings.host == "0.0.0.0"
    assert server.settings.port == 19090
    assert server.settings.sse_path == "/events"
    assert server.settings.message_path == "/inbox/"


@pytest.mark.parametrize("transport", ["stdio", "sse"])
def test_main_selects_configured_transport_and_disables_secret_bearing_http_logs(monkeypatch, transport):
    class StopServer:
        def run(self, transport: str):
            assert transport == expected_transport

    expected_transport = transport
    monkeypatch.setenv("APM_API_URL", "https://apm.example")
    monkeypatch.setenv("APM_API_KEY", "secret")
    monkeypatch.setenv("APM_MCP_TRANSPORT", transport)
    monkeypatch.setattr(server_module, "build_server", lambda settings: StopServer())
    server_module.main()
    assert logging.getLogger("httpx").level == logging.CRITICAL
    assert logging.getLogger("httpcore").level == logging.CRITICAL

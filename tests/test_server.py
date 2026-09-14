import pytest
import logging

from apm_mcp.config import Settings
from apm_mcp.server import build_server
from apm_mcp import server as server_module
from conftest import FakeClient


@pytest.mark.asyncio
async def test_exactly_eleven_read_only_tools_are_registered():
    settings = Settings(api_url="https://apm.example", api_key="secret")
    server = build_server(settings, FakeClient({}))
    tools = await server.list_tools()
    assert {tool.name for tool in tools} == {"GetAlarms", "GetAlarmDetails", "GetAlarmNotes", "SearchMonitors",
        "ListMonitors", "GetMonitorSummary", "GetServerContext", "GetMonitorRelationships",
        "GetMonitorGroupTopology", "ListMonitorMetrics", "GetPerformanceMetrics"}
    assert "secret" not in str(tools)
    forbidden = ("apikey", "api_key", "password", "token", "authorization")
    assert not any(term in str([(tool.name, tool.inputSchema) for tool in tools]).lower() for term in forbidden)


def test_main_disables_secret_bearing_http_logs(monkeypatch):
    class StopServer:
        def run(self, transport):
            assert transport == "stdio"

    monkeypatch.setenv("APM_API_URL", "https://apm.example")
    monkeypatch.setenv("APM_API_KEY", "secret")
    monkeypatch.setattr(server_module, "build_server", lambda settings: StopServer())
    server_module.main()
    assert logging.getLogger("httpx").level == logging.CRITICAL
    assert logging.getLogger("httpcore").level == logging.CRITICAL

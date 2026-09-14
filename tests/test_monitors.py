import pytest

from apm_mcp.errors import APMError
from apm_mcp.tools.monitors import get_monitor_summary, search_monitors
from conftest import FakeClient


@pytest.mark.asyncio
async def test_search_name_ip_multiple_and_none():
    payload = {"response": {"result": [
        {"RESOURCEID": "1", "DISPLAYNAME": "payment", "IPADDRESS": "192.0.2.1"},
        {"RESOURCEID": "2", "DISPLAYNAME": "payment-db", "IPADDRESS": "192.0.2.2"},
    ]}}
    client = FakeClient({"/AppManager/json/Search": payload})
    assert len((await search_monitors(client, "payment"))["monitors"]) == 2
    assert (await search_monitors(client, "192.0.2.1", "ipaddress", 1))["monitors"][0]["ip_address"] == "192.0.2.1"
    assert (await search_monitors(FakeClient({"/AppManager/json/Search": {"results": []}}), "none"))["monitors"] == []


@pytest.mark.asyncio
async def test_search_validation_and_malformed():
    with pytest.raises(APMError):
        await search_monitors(FakeClient({}), "x", "unsupported")
    with pytest.raises(APMError, match="unsupported"):
        await search_monitors(FakeClient({"/AppManager/json/Search": 7}), "x")


@pytest.mark.asyncio
async def test_summary_monitor_server_and_metrics():
    client = FakeClient({
        "/AppManager/json/ListMonitor": {"monitors": [{"RESOURCEID": "1", "DISPLAYNAME": "app", "HOSTIP": "192.0.2.9", "HEALTHSEVERITY": "clear", "MANAGED": "true"}]},
        "/AppManager/json/ListServer": {"servers": [{"resourceId": "9", "serverName": "host-1", "ipAddress": "192.0.2.9", "serverType": "Linux"}]},
        "/AppManager/xml/GetMonitorData": {"metrics": [{"attributeID": "5", "attributeName": "CPU", "value": "42"}]},
    })
    result = await get_monitor_summary(client, "1")
    assert result["host"]["hostname"] == "host-1"
    assert result["current_metrics"][0]["value"] == 42


@pytest.mark.asyncio
async def test_summary_partial_failure_does_not_fabricate_host():
    client = FakeClient({
        "/AppManager/json/ListMonitor": {"monitors": [{"RESOURCEID": "1", "DISPLAYNAME": "app"}]},
        "/AppManager/json/ListServer": APMError("upstream_error", "failed"),
        "/AppManager/xml/GetMonitorData": APMError("upstream_error", "failed"),
    })
    result = await get_monitor_summary(client, "1")
    assert result["host"]["ip_address"] is None
    assert result["current_metrics"] == []

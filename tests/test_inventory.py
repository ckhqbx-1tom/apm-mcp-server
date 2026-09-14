import pytest

from apm_mcp.errors import APMError
from apm_mcp.tools.inventory import get_server_context, list_monitor_metrics, list_monitors
from conftest import FakeClient, load_json, load_xml


@pytest.mark.asyncio
async def test_list_monitors_uses_official_filter_and_bounds_output():
    payload = load_json("list_monitor.json")
    payload["response"]["result"] *= 3
    client = FakeClient({"/AppManager/json/ListMonitor": payload})
    result = await list_monitors(client, monitor_type="Windows", health="critical", managed=True, page=1, page_size=2)
    assert client.calls[-1][1] == {"type": "Windows"}
    assert len(result["monitors"]) == 2
    assert result["has_more"] is True
    assert result["monitors"][0]["monitor_groups"][0]["resource_id"] == "10000029"


@pytest.mark.asyncio
async def test_list_monitors_resource_filter_and_validation():
    client = FakeClient({"/AppManager/json/ListMonitor": load_json("list_monitor.json")})
    result = await list_monitors(client, resource_id="10000035")
    assert result["monitors"][0]["resource_id"] == "10000035"
    assert client.calls[-1][1] == {"resourceid": "10000035"}
    with pytest.raises(APMError):
        await list_monitors(client, resource_id="1", monitor_type="Windows")


@pytest.mark.asyncio
async def test_get_server_context_resolves_service_by_host_ip():
    client = FakeClient({"/AppManager/json/ListMonitor": load_json("list_monitor.json"),
                         "/AppManager/json/ListServer": load_json("list_server.json")})
    result = await get_server_context(client, "10000035")
    assert client.calls[-1][1] == {"ipaddress": "192.0.2.10"}
    assert result["server"]["resource_id"] == "10000038"
    assert result["server"]["hostname"] == "server.example.invalid"
    assert result["related_monitors"][0]["resource_id"] == "10000043"


@pytest.mark.asyncio
async def test_get_server_context_does_not_guess_when_no_match():
    server = load_json("list_server.json")
    server["response"]["result"][0]["IPADDRESS"] = "198.51.100.20"
    client = FakeClient({"/AppManager/json/ListMonitor": load_json("list_monitor.json"),
                         "/AppManager/json/ListServer": server})
    result = await get_server_context(client, "10000035")
    assert result["server"]["ip_address"] is None


@pytest.mark.asyncio
async def test_list_monitor_metrics_preserves_attribute_ids():
    client = FakeClient({"/AppManager/xml/GetMonitorData": load_xml("get_monitor_data.xml")})
    result = await list_monitor_metrics(client, "10000035")
    assert [item["attribute_id"] for item in result["metrics"]] == ["1652", "1657"]
    assert result["metrics"][1]["current_value"] == 5.0

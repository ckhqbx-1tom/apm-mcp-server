import pytest

from apm_mcp.errors import APMError
from apm_mcp.tools.monitors import get_monitor_summary, search_monitors
from conftest import FakeClient, ResponseSequence, load_json


@pytest.mark.asyncio
async def test_official_search_shape_and_search_condition():
    client = FakeClient({"/AppManager/json/Search": load_json("search.json")})
    result = await search_monitors(client, "Linux", "monitortype")
    assert client.calls[-1][1] == {"query": "Linux", "searchCondition": "monitortype"}
    monitor = result["monitors"][0]
    assert monitor["health"] == "clear"
    assert monitor["health_severity"] == "5"
    assert monitor["availability"] == "up"
    assert monitor["availability_severity"] == "5"


@pytest.mark.asyncio
async def test_search_customfields_is_sent_upstream():
    client = FakeClient({"/AppManager/json/Search": {"response-code": "4000", "response": {"result": []}}})
    assert (await search_monitors(client, "team-a", "customfields"))["monitors"] == []
    assert client.calls[-1][1]["searchCondition"] == "customfields"


@pytest.mark.asyncio
async def test_search_validation_and_malformed():
    with pytest.raises(APMError):
        await search_monitors(FakeClient({}), "x", "unsupported")
    with pytest.raises(APMError, match="unsupported"):
        await search_monitors(FakeClient({"/AppManager/json/Search": 7}), "x")


@pytest.mark.asyncio
async def test_official_monitor_summary_fields_groups_and_last_poll():
    monitor_payload = load_json("list_monitor.json")
    server_payload = load_json("list_server.json")
    xml_payload = {"AppManager-response": {"result": {"response": {"response-code": "4000", "Monitorinfo": {
        "RESOURCEID": "10000035", "LASTPOLLEDTIME": "1714470960001",
        "Attribute": [{"AttributeID": "1657", "DISPLAYNAME": "CPU Utilization", "Units": "%", "Value": "5"}]
    }}}}}
    client = FakeClient({"/AppManager/json/ListMonitor": monitor_payload, "/AppManager/json/ListServer": server_payload,
                         "/AppManager/xml/GetMonitorData": xml_payload})
    result = await get_monitor_summary(client, "10000035")
    assert client.calls[0][1] == {"resourceid": "10000035"}
    assert result["health"] == "critical"
    assert result["availability"] == "up"
    assert result["monitor_groups"] == [
        {"resource_id": "10000029", "display_name": "Applications Manager"},
        {"resource_id": "10000105", "display_name": "Production"},
    ]
    assert result["last_polled_at"] == "2024-04-30T09:56:00+00:00"
    assert result["host"]["ip_address"] == "192.0.2.10"
    assert result["current_metrics"][0]["value"] == 5.0
    assert result["partial_errors"] == []


@pytest.mark.asyncio
async def test_summary_critical_enrichment_failure_is_not_swallowed():
    client = FakeClient({"/AppManager/json/ListMonitor": load_json("list_monitor.json"),
        "/AppManager/json/ListServer": APMError("authentication_error", "failed")})
    with pytest.raises(APMError) as caught:
        await get_monitor_summary(client, "10000035")
    assert caught.value.code == "authentication_error"


@pytest.mark.asyncio
async def test_summary_optional_enrichment_error_is_explicit():
    client = FakeClient({"/AppManager/json/ListMonitor": load_json("list_monitor.json"),
        "/AppManager/json/ListServer": APMError("not_found", "No matching server."),
        "/AppManager/xml/GetMonitorData": {}})
    result = await get_monitor_summary(client, "10000035")
    assert result["partial_errors"] == [{"source": "ListServer", "code": "not_found", "message": "No matching server."}]
    assert result["current_metrics"] == []


@pytest.mark.asyncio
async def test_list_monitor_targeted_query_has_limited_compatibility_fallback():
    client = FakeClient({
        "/AppManager/json/ListMonitor": ResponseSequence(
            APMError("invalid_request", "Directed query unsupported."), load_json("list_monitor.json")
        ),
        "/AppManager/json/ListServer": APMError("not_found", "No server."),
        "/AppManager/xml/GetMonitorData": {},
    })
    result = await get_monitor_summary(client, "10000035")
    assert result["resource_id"] == "10000035"
    assert client.calls[:2] == [
        ("/AppManager/json/ListMonitor", {"resourceid": "10000035"}),
        ("/AppManager/json/ListMonitor", {"type": "all"}),
    ]

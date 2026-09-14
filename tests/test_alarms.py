import pytest

from apm_mcp.errors import APMError
from apm_mcp.tools.alarms import get_alarm_details, get_alarms
from conftest import FakeClient, load_json


@pytest.mark.asyncio
async def test_official_alarm_shape_severity_and_server_parameters():
    client = FakeClient({"/api/v3/alarms": load_json("v3_alarms_extended.json")})
    result = await get_alarms(client, severity="critical", resource_id="10000035", acknowledged=False,
        start_time="1714000000000", end_time="1715000000000", page=2, page_size=25)
    assert client.calls[0][1] == {
        "view": "Extended", "severity": "Critical", "resourceId": "10000035",
        "monitorName": None, "monitorGroup": None,
        "acknowledged": "false", "startTime": "1714000000000", "endTime": "1715000000000",
        "page": 2, "rows": 25,
    }
    alarm = result["alarms"][0]
    assert alarm["severity"] == "critical"
    assert alarm["severity_code"] == 1
    assert result["has_more"] is False


@pytest.mark.asyncio
async def test_alarm_monitor_name_and_group_parameter_mapping():
    empty = {"data": [], "meta": {"total": 0, "records": 0, "page": 1}}
    name_client = FakeClient({"/api/v3/alarms": empty})
    await get_alarms(name_client, monitor_name="app")
    assert name_client.calls[-1][1]["monitorName"] == "app"
    group_client = FakeClient({"/api/v3/alarms": empty})
    await get_alarms(group_client, monitor_group="production")
    assert group_client.calls[-1][1]["monitorGroup"] == "production"
    with pytest.raises(APMError):
        await get_alarms(FakeClient({}), resource_id="1", monitor_group="group")


@pytest.mark.asyncio
async def test_alarm_empty_malformed_and_severity_validation():
    assert (await get_alarms(FakeClient({"/api/v3/alarms": {"data": [], "meta": {"total": 0}}})))["alarms"] == []
    with pytest.raises(APMError, match="unsupported"):
        await get_alarms(FakeClient({"/api/v3/alarms": {"alarms": []}}))
    with pytest.raises(APMError, match="severity"):
        await get_alarms(FakeClient({}), severity="1")


@pytest.mark.asyncio
async def test_alarm_details_resource_unique_and_null_alarm_id():
    payload = load_json("v3_alarms_extended.json")
    payload["data"] = payload["data"][:1]
    client = FakeClient({"/api/v3/alarms": payload, "/AppManager/json/ListMonitor": load_json("list_monitor.json")})
    result = await get_alarm_details(client, resource_id="10000035")
    assert result["alarm"]["alarm_id"] is None
    assert result["resource"]["host"] == "192.0.2.10"


@pytest.mark.asyncio
async def test_alarm_details_resource_and_attribute_unique():
    client = FakeClient({"/api/v3/alarms": load_json("v3_alarms_extended.json"), "/AppManager/json/ListMonitor": load_json("list_monitor.json")})
    result = await get_alarm_details(client, resource_id="10000035", attribute_id="1652")
    assert result["alarm"]["attribute_id"] == "1652"


@pytest.mark.asyncio
async def test_alarm_details_ambiguous_and_not_found():
    client = FakeClient({"/api/v3/alarms": load_json("v3_alarms_extended.json")})
    with pytest.raises(APMError) as caught:
        await get_alarm_details(client, resource_id="10000035")
    assert caught.value.code == "ambiguous_alarm"
    with pytest.raises(APMError) as caught:
        await get_alarm_details(client, resource_id="999")
    assert caught.value.code == "not_found"

import pytest

from apm_mcp.errors import APMError
from apm_mcp.tools.alarms import get_alarm_details, get_alarms
from conftest import FakeClient


@pytest.mark.asyncio
async def test_get_alarms_normal_filter_and_pagination(alarm_payload):
    payload = {"alarms": alarm_payload["alarms"] + [alarm_payload["alarms"][0] | {"alarmId": "a2", "severity": "warning"}]}
    client = FakeClient({"/api/v3/alarms": payload})
    result = await get_alarms(client, severity="critical", page_size=1)
    assert result["alarms"][0]["alarm_id"] == "a1"
    assert result["alarms"][0]["created_at"].startswith("2023-")
    assert result["page_size"] == 1


@pytest.mark.asyncio
async def test_get_alarms_empty_and_malformed():
    assert (await get_alarms(FakeClient({"/api/v3/alarms": {"alarms": []}})))["alarms"] == []
    with pytest.raises(APMError, match="unsupported"):
        await get_alarms(FakeClient({"/api/v3/alarms": "bad"}))


@pytest.mark.asyncio
async def test_alarm_details_exact_and_enriched(alarm_payload):
    client = FakeClient({
        "/api/v3/alarms": alarm_payload,
        "/AppManager/json/ListMonitor": {"monitors": [{"RESOURCEID": "10", "DISPLAYNAME": "Payments API", "IPADDRESS": "192.0.2.10"}]},
    })
    result = await get_alarm_details(client, alarm_id="a1")
    assert result["resource"]["display_name"] == "Payments API"
    assert result["resource"]["host"] == "192.0.2.10"


@pytest.mark.asyncio
async def test_alarm_details_missing_and_optional_fields():
    with pytest.raises(APMError) as caught:
        await get_alarm_details(FakeClient({"/api/v3/alarms": {"alarms": []}}), alarm_id="none")
    assert caught.value.code == "not_found"
    result = await get_alarm_details(FakeClient({"/api/v3/alarms": {"alarms": [{"resourceId": "1"}]}, "/AppManager/json/ListMonitor": {"monitors": []}}), resource_id="1")
    assert result["alarm"]["message"] is None


@pytest.mark.asyncio
async def test_alarm_details_resolves_v3_alarm_without_ids_by_exact_inventory_name():
    client = FakeClient({
        "/api/v3/alarms": {"data": [{"displayName": "app", "severityText": "Critical"}]},
        "/AppManager/json/ListMonitor": {"response": {"result": [{"RESOURCEID": "7", "DISPLAYNAME": "app"}]}},
    })
    result = await get_alarm_details(client, resource_id="7")
    assert result["alarm"]["resource_id"] == "7"
    assert result["resource"]["display_name"] == "app"

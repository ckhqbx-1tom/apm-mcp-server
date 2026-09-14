import pytest

from apm_mcp.errors import APMError
from apm_mcp.tools.metrics import get_performance_metrics
from conftest import FakeClient, load_json


@pytest.mark.asyncio
async def test_current_metrics_from_monitorinfo():
    payload = {"AppManager-response": {"result": {"response": {"response-code": "4000", "Monitorinfo": {
        "RESOURCEID": "1", "LASTPOLLEDTIME": "1700000000000",
        "Attribute": [{"AttributeID": "7", "DISPLAYNAME": "CPU", "Units": "%", "Value": "92.1"}]
    }}}}}
    result = await get_performance_metrics(FakeClient({"/AppManager/xml/GetMonitorData": payload}), "1")
    assert result["metrics"][0]["current_value"] == 92.1


@pytest.mark.asyncio
async def test_official_raw_polled_data_shape_and_request_params():
    client = FakeClient({"/AppManager/json/ShowPolledData": load_json("show_polled_data_raw.json")})
    result = await get_performance_metrics(client, "10000035", attribute_id="1657", period="20")
    metric = result["metrics"][0]
    assert metric["attribute_id"] == "1657"
    assert metric["name"] == "CPU Utilization"
    assert metric["unit"] == "%"
    assert metric["current_value"] is None
    assert [sample["value"] for sample in metric["samples"]] == [18.0, 12.5]
    assert metric["summary"] == {"min": 12.5, "max": 18.0, "avg": 15.25}
    assert client.calls[-1][1] == {"resourceid": "10000035", "attributeID": "1657", "period": "20", "startDate": None, "endDate": None}


@pytest.mark.asyncio
async def test_official_archive_polled_data_shape():
    client = FakeClient({"/AppManager/json/ShowPolledData": load_json("show_polled_data_archive.json")})
    metric = (await get_performance_metrics(client, "10000035", attribute_id="1657", period="-7"))["metrics"][0]
    assert [sample["value"] for sample in metric["samples"]] == [20.0, 30.0]
    assert metric["summary"] == {"min": 5.0, "max": 50.0, "avg": 25.0}


@pytest.mark.asyncio
async def test_historical_requires_attribute_and_safe_shape():
    with pytest.raises(APMError, match="attribute_id"):
        await get_performance_metrics(FakeClient({}), "1", period="20")
    with pytest.raises(APMError) as caught:
        await get_performance_metrics(FakeClient({"/AppManager/json/ShowPolledData": {"polledData": []}}), "1", attribute_id="7", period="20")
    assert caught.value.code == "unsupported_response"


@pytest.mark.asyncio
async def test_empty_current_metrics():
    result = await get_performance_metrics(FakeClient({"/AppManager/xml/GetMonitorData": {}}), "1")
    assert result == {"resource_id": "1", "metrics": []}

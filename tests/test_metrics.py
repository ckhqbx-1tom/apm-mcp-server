import pytest

from apm_mcp.tools.metrics import get_performance_metrics
from conftest import FakeClient


@pytest.mark.asyncio
async def test_current_metrics_and_malformed_number():
    client = FakeClient({"/AppManager/xml/GetMonitorData": {"metrics": [
        {"attributeID": "7", "attributeName": "CPU", "unit": "%", "value": "92.1"},
        {"attributeID": "8", "attributeName": "State", "value": "unknown"},
    ]}})
    result = await get_performance_metrics(client, "1")
    assert result["metrics"][0]["current_value"] == 92.1
    assert result["metrics"][1]["current_value"] is None


@pytest.mark.asyncio
async def test_historical_metrics_attribute_and_summary():
    client = FakeClient({"/AppManager/json/ShowPolledData": {"polledData": [
        {"attributeID": "7", "attributeName": "CPU", "value": "10", "timestamp": "1700000000000"},
        {"attributeID": "7", "attributeName": "CPU", "value": "30", "timestamp": "1700000060000"},
        {"attributeID": "8", "attributeName": "Memory", "value": "50"},
    ]}})
    result = await get_performance_metrics(client, "1", attribute_id="7", period="today")
    metric = result["metrics"][0]
    assert metric["attribute_id"] == "7"
    assert metric["summary"] == {"min": 10.0, "max": 30.0, "avg": 20.0}
    assert metric["samples"][0]["timestamp"].startswith("2023-")


@pytest.mark.asyncio
async def test_empty_metrics():
    result = await get_performance_metrics(FakeClient({"/AppManager/xml/GetMonitorData": {"metrics": []}}), "1")
    assert result == {"resource_id": "1", "metrics": []}

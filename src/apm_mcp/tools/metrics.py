from __future__ import annotations

from typing import Any

from ..client import APMClient
from ..errors import APMError
from ..normalization.apm import normalize_monitor_data, normalize_show_polled_data


async def get_performance_metrics(
    client: APMClient, resource_id: str, attribute_id: str | None = None,
    start_time: str | None = None, end_time: str | None = None, period: str | None = None,
) -> dict[str, Any]:
    if not resource_id.strip():
        raise APMError("invalid_request", "resource_id must not be empty.")
    historical = any((start_time, end_time, period))
    if historical:
        if not attribute_id:
            raise APMError("invalid_request", "attribute_id is required for historical metrics.")
        if (start_time or end_time) and not (start_time and end_time):
            raise APMError("invalid_request", "start_time and end_time must be provided together.")
        effective_period = period or ("4" if start_time and end_time else None)
        params = {
            "resourceid": resource_id, "attributeID": attribute_id, "period": effective_period,
            "startDate": start_time, "endDate": end_time,
        }
        payload = await client.get_json("/AppManager/json/ShowPolledData", params)
        metrics = normalize_show_polled_data(payload, resource_id)
        metrics = [metric for metric in metrics if str(metric["attribute_id"]) == attribute_id]
        return {"resource_id": resource_id, "metrics": metrics}

    payload = await client.get_xml("/AppManager/xml/GetMonitorData", {"resourceid": resource_id})
    _, normalized = normalize_monitor_data(payload)
    if attribute_id is not None:
        normalized = [item for item in normalized if str(item["attribute_id"]) == attribute_id]
    metrics = []
    for item in normalized[:500]:
        value = item["value"] if isinstance(item["value"], float) else None
        metrics.append({
            "attribute_id": item["attribute_id"], "name": item["name"], "unit": item["unit"],
            "current_value": value, "samples": [],
            "summary": {"min": value, "max": value, "avg": value},
        })
    return {"resource_id": resource_id, "metrics": metrics}

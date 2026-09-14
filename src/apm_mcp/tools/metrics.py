from __future__ import annotations

from collections import defaultdict
from typing import Any

from ..client import APMClient
from ..errors import APMError
from ..normalization.apm import normalize_metric, records


async def get_performance_metrics(
    client: APMClient, resource_id: str, attribute_id: str | None = None,
    start_time: str | None = None, end_time: str | None = None, period: str | None = None,
) -> dict[str, Any]:
    if not resource_id.strip():
        raise APMError("invalid_request", "resource_id must not be empty.")
    historical = any((start_time, end_time, period))
    params = {"resourceid": resource_id, "attributeID": attribute_id, "period": period, "startDate": start_time, "endDate": end_time}
    if historical:
        payload = await client.get_json("/AppManager/json/ShowPolledData", params)
    else:
        payload = await client.get_xml("/AppManager/xml/GetMonitorData", {"resourceid": resource_id})
    if not isinstance(payload, (dict, list)):
        raise APMError("unsupported_response", "Applications Manager returned an unsupported metric response.")
    rows = records(payload, ("metrics", "metric", "attributes", "attribute", "data", "rows", "row", "polledData"))
    normalized = [normalize_metric(row) for row in rows]
    if attribute_id is not None:
        normalized = [item for item in normalized if str(item["attribute_id"]) == attribute_id]
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for item in normalized[:5000]:
        grouped[str(item["attribute_id"] or item["name"] or "unknown")].append(item)
    metrics = []
    for items in grouped.values():
        values = [item["value"] for item in items if isinstance(item["value"], float)]
        samples = [{"timestamp": item["timestamp"], "value": item["value"]} for item in items]
        metrics.append({
            "attribute_id": items[0]["attribute_id"], "name": items[0]["name"], "unit": items[0]["unit"],
            "current_value": None if historical else items[-1]["value"], "samples": samples if historical else [],
            "summary": {
                "min": min(values) if values else None, "max": max(values) if values else None,
                "avg": sum(values) / len(values) if values else None,
            },
        })
    return {"resource_id": resource_id, "metrics": metrics}

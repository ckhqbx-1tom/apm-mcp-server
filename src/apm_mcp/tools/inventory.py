from __future__ import annotations

from typing import Any

from ..client import APMClient
from ..errors import APMError
from ..normalization.apm import field, normalize_monitor, normalize_monitor_data, records
from .alarms import _get_monitor

MAX_RESULTS = 500


async def list_monitors(
    client: APMClient, resource_id: str | None = None, monitor_type: str | None = None,
    monitor_group: str | None = None, managed: bool | None = None, health: str | None = None,
    availability: str | None = None, page: int = 1, page_size: int = 100,
) -> dict[str, Any]:
    if page < 1 or not 1 <= page_size <= MAX_RESULTS:
        raise APMError("invalid_request", f"page must be positive and page_size must be 1-{MAX_RESULTS}.")
    if resource_id and monitor_type:
        raise APMError("invalid_request", "resource_id and monitor_type cannot be combined by ListMonitor.")
    params = {"resourceid": resource_id} if resource_id else {"type": monitor_type or "all"}
    payload = await client.get_json("/AppManager/json/ListMonitor", params)
    rows = records(payload, ("Monitor", "result"))
    monitors = [normalize_monitor(row) for row in rows]
    if resource_id:
        monitors = [item for item in monitors if str(item["resource_id"]) == resource_id]
    if monitor_group:
        monitors = [item for item in monitors if any(
            monitor_group.lower() in {str(group.get("resource_id") or "").lower(), str(group.get("display_name") or "").lower()}
            for group in item["monitor_groups"]
        )]
    if managed is not None:
        monitors = [item for item in monitors if item["managed"] is managed]
    if health:
        monitors = [item for item in monitors if item["health"] == health.lower()]
    if availability:
        monitors = [item for item in monitors if item["availability"] == availability.lower()]
    start = (page - 1) * page_size
    return {"monitors": monitors[start:start + page_size], "page": page, "page_size": page_size,
            "has_more": len(monitors) > start + page_size}


async def get_server_context(client: APMClient, resource_id: str) -> dict[str, Any]:
    if not resource_id.strip():
        raise APMError("invalid_request", "resource_id must not be empty.")
    monitor = await _get_monitor(client, resource_id)
    params = {"ipaddress": monitor["ip_address"]} if monitor["ip_address"] else {"type": "all"}
    payload = await client.get_json("/AppManager/json/ListServer", params)
    rows = records(payload, ("Server", "result"))
    candidates = []
    for row in rows:
        services = _items(field(row, "Service", "services"))
        server_id = field(row, "RESOURCEID", "resourceId")
        if (str(server_id) == resource_id or any(str(field(service, "RESOURCEID", "resourceId")) == resource_id for service in services)
                or (monitor["ip_address"] and field(row, "IPADDRESS", "ipAddress") == monitor["ip_address"])):
            candidates.append((row, services))
    if len(candidates) > 1:
        raise APMError("ambiguous_resource", "Multiple servers match the supplied resource ID.")
    if not candidates:
        return {"resource_id": resource_id, "server": {"resource_id": None, "hostname": None,
                "ip_address": None, "server_type": None}, "related_monitors": []}
    server, services = candidates[0]
    return {"resource_id": resource_id, "server": {
        "resource_id": field(server, "RESOURCEID", "resourceId"),
        "hostname": field(server, "Name", "DISPLAYNAME", "hostname"),
        "ip_address": field(server, "IPADDRESS", "ipAddress"),
        "server_type": field(server, "TYPE", "serverType"),
    }, "related_monitors": [normalize_monitor(item) for item in services][:MAX_RESULTS]}


async def list_monitor_metrics(client: APMClient, resource_id: str) -> dict[str, Any]:
    if not resource_id.strip():
        raise APMError("invalid_request", "resource_id must not be empty.")
    payload = await client.get_xml("/AppManager/xml/GetMonitorData", {"resourceid": resource_id})
    _, metrics = normalize_monitor_data(payload)
    return {"resource_id": resource_id, "metrics": [{
        "attribute_id": item["attribute_id"], "name": item["name"], "unit": item["unit"],
        "current_value": item["value"] if isinstance(item["value"], float) else None,
    } for item in metrics[:MAX_RESULTS]]}


def _items(value: Any) -> list[dict[str, Any]]:
    if isinstance(value, dict):
        return [value]
    if isinstance(value, list):
        return [item for item in value if isinstance(item, dict)]
    return []

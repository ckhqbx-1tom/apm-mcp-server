from __future__ import annotations

from typing import Any

from ..client import APMClient
from ..errors import APMError
from ..normalization.apm import field, normalize_metric, normalize_monitor, records

SEARCH_BY = {"all", "displayname", "monitortype", "ipaddress", "customfields"}


async def search_monitors(client: APMClient, query: str, search_by: str = "all", limit: int = 50) -> dict[str, Any]:
    if not query.strip():
        raise APMError("invalid_request", "query must not be empty.")
    if search_by not in SEARCH_BY:
        raise APMError("invalid_request", f"search_by must be one of: {', '.join(sorted(SEARCH_BY))}.")
    if not 1 <= limit <= 500:
        raise APMError("invalid_request", "limit must be between 1 and 500.")
    payload = await client.get_json("/AppManager/json/Search", {"query": query})
    if not isinstance(payload, (dict, list)):
        raise APMError("unsupported_response", "Applications Manager returned an unsupported search response.")
    monitors = [normalize_monitor(item) for item in records(payload, ("monitors", "monitor", "data", "result", "results", "searchResults"))]
    if search_by != "all":
        field_name = {
            "displayname": "display_name", "monitortype": "monitor_type", "ipaddress": "ip_address",
        }.get(search_by)
        if field_name:
            monitors = [item for item in monitors if query.lower() in str(item[field_name] or "").lower()]
    return {"monitors": monitors[:limit]}


async def get_monitor_summary(client: APMClient, resource_id: str) -> dict[str, Any]:
    if not resource_id.strip():
        raise APMError("invalid_request", "resource_id must not be empty.")
    payload = await client.get_json("/AppManager/json/ListMonitor", {"type": "all"})
    if not isinstance(payload, (dict, list)):
        raise APMError("unsupported_response", "Applications Manager returned an unsupported monitor response.")
    rows = records(payload, ("monitors", "monitor", "data", "result", "results"))
    normalized = [normalize_monitor(row) for row in rows]
    monitor = next((item for item in normalized if str(item["resource_id"]) == resource_id), None)
    if monitor is None:
        raise APMError("not_found", "The requested monitor was not found.")
    host = {"hostname": None, "ip_address": monitor["ip_address"], "server_type": None, "resource_id": None}
    groups: list[Any] = []
    related: list[Any] = []
    current_metrics: list[dict[str, Any]] = []
    last_polled_at = None
    try:
        servers = await client.get_json("/AppManager/json/ListServer", {"type": "all"})
        server_rows = records(servers, ("servers", "server", "data", "result", "results"))
        server = next((row for row in server_rows if (
            str(field(row, "resourceId", "RESOURCEID")) == resource_id
            or (monitor["ip_address"] and field(row, "ipAddress", "IPADDRESS") == monitor["ip_address"])
        )), None)
        if server:
            host = {
                "hostname": field(server, "serverName", "hostName", "displayName"),
                "ip_address": field(server, "ipAddress", "IPADDRESS") or host["ip_address"],
                "server_type": field(server, "serverType", "type"),
                "resource_id": field(server, "resourceId", "RESOURCEID"),
            }
            related_value = field(server, "associatedMonitors", "services")
            related = related_value if isinstance(related_value, list) else []
    except APMError:
        pass
    try:
        data = await client.get_xml("/AppManager/xml/GetMonitorData", {"resourceid": resource_id})
        metric_rows = records(data, ("metrics", "metric", "attribute", "attributes", "data", "row"))
        current_metrics = [normalize_metric(row) for row in metric_rows][:100]
        timestamps = [item["timestamp"] for item in current_metrics if item["timestamp"]]
        last_polled_at = timestamps[0] if timestamps else None
    except APMError:
        pass
    return {
        "resource_id": monitor["resource_id"], "display_name": monitor["display_name"],
        "monitor_type": monitor["monitor_type"], "health": monitor["health"],
        "availability": monitor["availability"], "managed": monitor["managed"],
        "last_polled_at": last_polled_at, "host": host, "monitor_groups": groups,
        "related_services": related, "current_metrics": current_metrics,
    }

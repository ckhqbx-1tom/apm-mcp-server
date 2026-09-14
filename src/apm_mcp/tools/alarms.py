from __future__ import annotations

from typing import Any

from ..client import APMClient
from ..errors import APMError
from ..normalization.apm import normalize_alarm, normalize_monitor, records

MAX_PAGE_SIZE = 500


def _valid_payload(payload: Any) -> None:
    if not isinstance(payload, (dict, list)):
        raise APMError("unsupported_response", "Applications Manager returned an unsupported alarm response.")


async def get_alarms(
    client: APMClient, severity: str | None = None, resource_id: str | None = None,
    monitor_name: str | None = None, monitor_group: str | None = None,
    acknowledged: bool | None = None, start_time: str | None = None,
    end_time: str | None = None, page: int = 1, page_size: int = 100,
) -> dict[str, Any]:
    if page < 1 or not 1 <= page_size <= MAX_PAGE_SIZE:
        raise APMError("invalid_request", f"page must be positive and page_size must be 1-{MAX_PAGE_SIZE}.")
    # v3 parameter support differs by release; retrieve alarms and apply stable MCP filters locally.
    payload = await client.get_json("/api/v3/alarms")
    _valid_payload(payload)
    raw = records(payload, ("alarms", "alarm", "data", "results"))
    alarms = [normalize_alarm(item) for item in raw]
    # Apply filters locally too because older installations may ignore newer query fields.
    if severity is not None:
        alarms = [a for a in alarms if str(a["severity"]).lower() == severity.lower()]
    if resource_id is not None:
        alarms = [a for a in alarms if str(a["resource_id"]) == resource_id]
    if monitor_name is not None:
        alarms = [a for a in alarms if monitor_name.lower() in str(a["resource_name"] or "").lower()]
    if acknowledged is not None:
        alarms = [a for a in alarms if a["acknowledged"] is acknowledged]
    start = (page - 1) * page_size
    has_more = len(alarms) > start + page_size
    return {"alarms": alarms[start:start + page_size], "page": page, "page_size": page_size, "has_more": has_more}


async def get_alarm_details(
    client: APMClient, alarm_id: str | None = None,
    resource_id: str | None = None, attribute_id: str | None = None,
) -> dict[str, Any]:
    if not any((alarm_id, resource_id, attribute_id)):
        raise APMError("invalid_request", "Provide alarm_id, resource_id, or attribute_id.")
    result = await get_alarms(client, page_size=MAX_PAGE_SIZE)
    matches = result["alarms"]
    if alarm_id is not None:
        matches = [item for item in matches if str(item["alarm_id"]) == alarm_id]
    if resource_id is not None:
        direct = [item for item in matches if str(item["resource_id"]) == resource_id]
        if direct:
            matches = direct
        else:
            inventory = await client.get_json("/AppManager/json/ListMonitor", {"type": "all"})
            monitor_rows = records(inventory, ("monitors", "monitor", "data", "result", "results"))
            target = next((normalize_monitor(row) for row in monitor_rows
                           if str(normalize_monitor(row)["resource_id"]) == resource_id), None)
            matches = [item for item in matches if target and item["resource_name"] == target["display_name"]]
            for item in matches:
                item["resource_id"] = resource_id
    if attribute_id is not None:
        matches = [item for item in matches if str(item["attribute_id"]) == attribute_id]
    if not matches:
        raise APMError("not_found", "The requested alarm was not found.")
    alarm = matches[0]
    resource = {
        "resource_id": alarm["resource_id"], "display_name": alarm["resource_name"],
        "monitor_type": alarm["monitor_type"], "host": None,
    }
    if alarm["resource_id"]:
        try:
            payload = await client.get_json("/AppManager/json/ListMonitor", {"type": "all"})
            monitor_rows = records(payload, ("monitors", "monitor", "data", "result", "results"))
            monitor = next((normalize_monitor(row) for row in monitor_rows
                            if str(normalize_monitor(row)["resource_id"]) == str(alarm["resource_id"])), None)
            if monitor:
                resource.update({
                    "display_name": monitor["display_name"] or resource["display_name"],
                    "monitor_type": monitor["monitor_type"] or resource["monitor_type"],
                    "host": monitor["ip_address"],
                })
        except APMError:
            pass
    return {"alarm": alarm, "resource": resource}

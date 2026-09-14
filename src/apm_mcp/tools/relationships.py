from __future__ import annotations

from typing import Any

from ..client import APMClient
from ..errors import APMError
from ..normalization.apm import field, normalize_monitor, records
from .inventory import _items
from .alarms import _get_monitor

MAX_RELATIONSHIPS = 500


async def get_monitor_relationships(
    client: APMClient, resource_id: str, attribute_id: str | None = None,
) -> dict[str, Any]:
    if not resource_id.strip():
        raise APMError("invalid_request", "resource_id must not be empty.")
    if attribute_id is None:
        monitor = await _get_monitor(client, resource_id)
        derived = monitor.get("health_attribute_id")
        if derived is None:
            raise APMError("invalid_request", "attribute_id is required when ListMonitor has no health attribute ID.")
        attribute_id = str(derived)
    payload = await client.get_xml("/AppManager/xml/listDependencies", {
        "resourceid": resource_id, "attributeid": attribute_id,
    })
    dependency_rows = records(payload, ("Dependency", "Dependencies", "DependentResource"))
    relationships = []
    for row in dependency_rows[:MAX_RELATIONSHIPS]:
        target_id = field(row, "dependentResourceId", "DEPENDENTRESOURCEID", "resourceId", "RESOURCEID")
        relationships.append({
            "direction": "dependency", "resource_id": target_id,
            "display_name": field(row, "displayName", "DISPLAYNAME", "resourceName", "RESOURCENAME"),
            "monitor_type": field(row, "monitorType", "TYPE"),
            "attribute_id": field(row, "attributeId", "ATTRIBUTEID"),
        })
    return {"resource_id": resource_id, "relationships": relationships}


async def get_monitor_group_topology(
    client: APMClient, monitor_group_id: str | None = None,
    monitor_group_name: str | None = None, limit: int = 500,
) -> dict[str, Any]:
    if not any((monitor_group_id, monitor_group_name)):
        raise APMError("invalid_request", "monitor_group_id or monitor_group_name is required.")
    if monitor_group_id and monitor_group_name:
        raise APMError("invalid_request", "Provide only one monitor group identifier.")
    if not 1 <= limit <= MAX_RELATIONSHIPS:
        raise APMError("invalid_request", f"limit must be 1-{MAX_RELATIONSHIPS}.")
    params = {"groupId": monitor_group_id} if monitor_group_id else {"groupName": monitor_group_name}
    payload = await client.get_json("/AppManager/json/ListMGDetails", params)
    rows = records(payload, ("MonitorGroup", "result"))
    matches = [row for row in rows if (
        monitor_group_id and str(field(row, "RESOURCEID", "resourceId")) == monitor_group_id
        or monitor_group_name and str(field(row, "DISPLAYNAME", "NAME")).lower() == monitor_group_name.lower()
    )]
    if not matches:
        raise APMError("not_found", "The requested monitor group was not found.")
    if len(matches) > 1:
        raise APMError("ambiguous_resource", "Multiple monitor groups match the supplied identifier.")
    group = matches[0]
    members = [normalize_monitor(item) for item in _items(field(group, "Monitors", "Monitor"))][:limit]
    children = [normalize_monitor(item) for item in _items(field(group, "SubMonitorGroup", "SubMonitorGroups"))][:limit]
    return {"group": {"resource_id": field(group, "RESOURCEID", "resourceId"),
            "display_name": field(group, "DISPLAYNAME", "NAME")}, "members": members, "child_groups": children}

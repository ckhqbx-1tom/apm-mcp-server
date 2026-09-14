from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Iterable


def _key(value: str) -> str:
    return "".join(character for character in value.lower() if character.isalnum())


def field(item: dict[str, Any], *names: str) -> Any:
    indexed = {_key(str(key)): value for key, value in item.items()}
    for name in names:
        value = indexed.get(_key(name))
        if value not in (None, ""):
            return value
    return None


def records(payload: Any, collection_names: Iterable[str]) -> list[dict[str, Any]]:
    """Find a known record collection without accepting arbitrary malformed data."""
    wanted = {_key(name) for name in collection_names}
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if not isinstance(payload, dict):
        return []
    for key, value in payload.items():
        if _key(str(key)) in wanted:
            if isinstance(value, list):
                return [item for item in value if isinstance(item, dict)]
            if isinstance(value, dict):
                # XML conversion commonly wraps repeated entries one level deeper.
                nested = records(value, (*collection_names, "monitor", "metric", "data", "row"))
                return nested or [value]
    for value in payload.values():
        if isinstance(value, dict):
            found = records(value, collection_names)
            if found:
                return found
    return []


def normalize_timestamp(value: Any) -> str | None:
    if value in (None, ""):
        return None
    raw = str(value).strip()
    try:
        numeric = float(raw)
        if numeric > 10_000_000_000:
            numeric /= 1000
        return datetime.fromtimestamp(numeric, tz=timezone.utc).isoformat()
    except (ValueError, OverflowError, OSError):
        pass
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        return parsed.isoformat()
    except ValueError:
        return raw


def _bool(value: Any) -> bool | None:
    if isinstance(value, bool):
        return value
    if value is None:
        return None
    lowered = str(value).lower()
    if lowered in {"true", "yes", "1", "acknowledged", "managed"}:
        return True
    if lowered in {"false", "no", "0", "unacknowledged", "unmanaged"}:
        return False
    return None


def normalize_alarm(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "alarm_id": field(item, "alarmId", "alarm_id", "entityId"),
        "resource_id": field(item, "resourceId", "RESOURCEID", "resource_id"),
        "resource_name": field(item, "displayName", "resourceName", "DISPLAYNAME"),
        "monitor_type": field(item, "monitorType", "monitorTypeDisplayName", "TYPE", "monitor_type"),
        "parent_resource_id": field(item, "parentResourceId", "parent_resource_id"),
        "severity": field(item, "severity", "severityText", "SEVERITY"),
        "message": field(item, "message", "healthMessage", "MESSAGE"),
        "attribute_id": field(item, "attributeId", "attributeID", "ATTRIBUTEID"),
        "attribute_name": field(item, "attributeName", "attributeDisplayName", "ATTRIBUTENAME"),
        "acknowledged": _bool(field(item, "acknowledged", "isAcknowledged", "ACKNOWLEDGED")),
        "created_at": normalize_timestamp(field(item, "alertCreationTime", "createdAt", "startTime")),
        "modified_at": normalize_timestamp(field(item, "alertModifiedTime", "modifiedAt", "endTime")),
        "latest_note": field(item, "latestNote", "note"),
    }


def normalize_monitor(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "resource_id": field(item, "resourceId", "RESOURCEID", "resource_id"),
        "display_name": field(item, "displayName", "DISPLAYNAME", "name"),
        "monitor_type": field(item, "monitorType", "TYPE", "monitor_type"),
        "health": field(item, "health", "HEALTHSEVERITY", "healthStatus"),
        "availability": field(item, "availability", "AVAILABILITYSEVERITY", "availabilityStatus"),
        "health_message": field(item, "healthMessage", "HEALTHMESSAGE"),
        "availability_message": field(item, "availabilityMessage", "AVAILABILITYMESSAGE"),
        "ip_address": field(item, "ipAddress", "IPADDRESS", "HOSTIP", "host"),
        "managed": _bool(field(item, "managed", "managedStatus", "MANAGED")),
    }


def normalize_metric(item: dict[str, Any]) -> dict[str, Any]:
    raw_value = field(item, "value", "currentValue", "VALUE", "attributeValue")
    try:
        value: float | str | None = float(raw_value) if raw_value not in (None, "") else None
    except (TypeError, ValueError):
        value = None
    return {
        "attribute_id": field(item, "attributeId", "attributeID", "ATTRIBUTEID", "id"),
        "name": field(item, "attributeName", "name", "DISPLAYNAME"),
        "unit": field(item, "unit", "UNITS"),
        "value": value,
        "timestamp": normalize_timestamp(field(item, "timestamp", "time", "collectionTime", "lastPolledTime")),
    }

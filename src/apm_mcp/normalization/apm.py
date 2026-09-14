from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Iterable

from ..errors import APMError


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
    severity_code = field(item, "severity", "SEVERITY")
    severity_text = field(item, "severityText")
    if severity_text is not None:
        severity = str(severity_text).strip().lower()
    else:
        attribute = str(field(item, "attributeName", "attributeDisplayName") or "").lower()
        severity = {"1": "down" if "availability" in attribute else "critical", "4": "warning", "5": "up" if "availability" in attribute else "clear"}.get(str(severity_code))
    return {
        "alarm_id": field(item, "alarmId", "alarm_id", "entityId"),
        "resource_id": field(item, "resourceId", "RESOURCEID", "resource_id"),
        "resource_name": field(item, "displayName", "resourceName", "DISPLAYNAME"),
        "monitor_type": field(item, "monitorType", "monitorTypeDisplayName", "TYPE", "monitor_type"),
        "parent_resource_id": field(item, "parentResourceId", "parent_resource_id"),
        "severity": severity,
        "severity_code": severity_code,
        "message": field(item, "message", "healthMessage", "MESSAGE"),
        "attribute_id": field(item, "attributeId", "attributeID", "ATTRIBUTEID"),
        "attribute_name": field(item, "attributeName", "attributeDisplayName", "ATTRIBUTENAME"),
        "acknowledged": _bool(field(item, "acknowledged", "isAcknowledged", "ACKNOWLEDGED")),
        "created_at": normalize_timestamp(field(item, "alertCreationTime", "createdAt", "startTime")),
        "modified_at": normalize_timestamp(field(item, "alertModifiedTimeInMillis", "alertModifiedTime", "modifiedAt", "endTime")),
        "latest_note": field(item, "latestNote", "note"),
    }


def normalize_monitor(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "resource_id": field(item, "resourceId", "RESOURCEID", "resource_id"),
        "display_name": field(item, "displayName", "DISPLAYNAME", "name"),
        "monitor_type": field(item, "monitorType", "TYPE", "monitor_type"),
        "health": _lower(field(item, "healthStatus", "HEALTHSTATUS", "health")),
        "availability": _lower(field(item, "availabilityStatus", "AVAILABILITYSTATUS", "availability")),
        "health_severity": field(item, "healthSeverity", "HEALTHSEVERITY"),
        "availability_severity": field(item, "availabilitySeverity", "AVAILABILITYSEVERITY"),
        "health_attribute_id": field(item, "healthAttributeId", "HEALTHATTRIBUTEID"),
        "availability_attribute_id": field(item, "availabilityAttributeId", "AVAILABILITYATTRIBUTEID"),
        "health_message": field(item, "healthMessage", "HEALTHMESSAGE"),
        "availability_message": field(item, "availabilityMessage", "AVAILABILITYMESSAGE"),
        "ip_address": field(item, "ipAddress", "IPADDRESS", "HOSTIP", "host"),
        "managed": _bool(field(item, "managed", "managedStatus", "MANAGED")),
        "monitor_groups": normalize_groups(field(item, "associatedGroups", "ASSOCIATEDGROUPS")),
        "last_polled_at": normalize_timestamp(field(item, "LAST_POLLED_TIME", "lastPolledTime", "LASTPOLLEDTIME")),
    }


def _lower(value: Any) -> str | None:
    return str(value).strip().lower() if value not in (None, "") else None


def normalize_groups(value: Any) -> list[dict[str, Any]]:
    if isinstance(value, list):
        return [item for item in value if isinstance(item, dict)]
    if not isinstance(value, str) or not value.strip():
        return []
    groups = []
    for entry in value.split(","):
        parsed: dict[str, Any] = {}
        for part in entry.split(";"):
            key, separator, raw = part.partition(":")
            if separator:
                parsed[_key(key)] = raw.strip()
        if parsed:
            groups.append({"resource_id": parsed.get("id"), "display_name": parsed.get("name")})
    return groups


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


def normalize_monitor_data(payload: Any) -> tuple[dict[str, Any] | None, list[dict[str, Any]]]:
    if payload == {}:
        return None, []
    monitor_rows = records(payload, ("Monitorinfo",))
    if not monitor_rows:
        raise APMError("unsupported_response", "Applications Manager monitor data has no Monitorinfo record.")
    monitor_info = monitor_rows[0]
    attributes = monitor_info.get("Attribute", [])
    if isinstance(attributes, dict):
        attributes = [attributes]
    if not isinstance(attributes, list):
        raise APMError("parse_error", "Applications Manager monitor attributes are malformed.")
    metrics = [normalize_metric(item) for item in attributes if isinstance(item, dict)]
    return normalize_monitor(monitor_info), metrics


def normalize_show_polled_data(payload: Any, expected_resource_id: str) -> list[dict[str, Any]]:
    if not isinstance(payload, dict):
        raise APMError("unsupported_response", "Applications Manager polled data is not an object.")
    response = payload.get("response")
    if not isinstance(response, dict) or "result" not in response:
        raise APMError("unsupported_response", "Applications Manager polled data has no response.result collection.")
    result = response["result"]
    if not isinstance(result, list):
        raise APMError("parse_error", "Applications Manager polled data result is malformed.")
    metrics: list[dict[str, Any]] = []
    for outer in result:
        if not isinstance(outer, dict):
            raise APMError("parse_error", "Applications Manager polled metric is malformed.")
        resource_id = field(outer, "ResourceId")
        attribute_id = field(outer, "AttributeID")
        name = field(outer, "AttributeName")
        unit = field(outer, "Unit")
        if resource_id is not None and str(resource_id) != expected_resource_id:
            continue
        raw_data = outer.get("RawData")
        archive_data = outer.get("ArchiveData")
        if raw_data is None and archive_data is None:
            if str(field(outer, "Status") or "").upper() not in {"", "SUCCESS"}:
                raise APMError("upstream_error", "Applications Manager could not produce polled data.")
            raw_data = []
        source = raw_data if raw_data is not None else archive_data
        if isinstance(source, dict):
            source = [source]
        if not isinstance(source, list):
            raise APMError("parse_error", "Applications Manager metric samples are malformed.")
        samples: list[dict[str, Any]] = []
        mins: list[float] = []
        maxes: list[float] = []
        averages: list[float] = []
        malformed_values = 0
        for sample in source:
            if not isinstance(sample, dict):
                raise APMError("parse_error", "Applications Manager metric sample is malformed.")
            timestamp = normalize_timestamp(field(sample, "CollectionTime", "ArchivedTime", "timestamp", "time"))
            raw_value = field(sample, "Value", "AvgValue", "avg", "average")
            value = _number(raw_value)
            if raw_value not in (None, "") and value is None:
                malformed_values += 1
                continue
            samples.append({"timestamp": timestamp, "value": value})
            minimum = _number(field(sample, "MinValue", "min"))
            maximum = _number(field(sample, "MaxValue", "max"))
            average = _number(field(sample, "AvgValue", "avg", "average"))
            if minimum is not None: mins.append(minimum)
            if maximum is not None: maxes.append(maximum)
            if average is not None: averages.append(average)
        if malformed_values and not samples:
            raise APMError("parse_error", "Applications Manager metric values are malformed.")
        values = [sample["value"] for sample in samples if isinstance(sample["value"], float)]
        metrics.append({
            "attribute_id": attribute_id, "name": name, "unit": unit, "current_value": None,
            "samples": samples,
            "summary": {
                "min": min(mins) if mins else (min(values) if values else None),
                "max": max(maxes) if maxes else (max(values) if values else None),
                "avg": sum(averages) / len(averages) if averages else (sum(values) / len(values) if values else None),
            },
        })
    return metrics


def _number(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None

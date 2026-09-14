from __future__ import annotations

from typing import Any

from ..client import APMClient
from ..errors import APMError
from ..normalization.apm import normalize_alarm, normalize_monitor, records

MAX_PAGE_SIZE = 500
MAX_DETAIL_PAGES = 10_000
ALARM_SEVERITIES = {"critical", "warning", "clear", "down", "up"}
FAIL_CLOSED_ERRORS = {"authentication_error", "authorization_error", "tls_error", "connection_error", "timeout", "parse_error"}


def _alarm_rows(payload: Any) -> list[dict[str, Any]]:
    if not isinstance(payload, dict) or not isinstance(payload.get("data"), list):
        raise APMError("unsupported_response", "Applications Manager returned an unsupported alarm response.")
    if not all(isinstance(item, dict) for item in payload["data"]):
        raise APMError("parse_error", "Applications Manager returned malformed alarm records.")
    return payload["data"]


async def get_alarms(
    client: APMClient, severity: str | None = None, resource_id: str | None = None,
    monitor_name: str | None = None, monitor_group: str | None = None,
    acknowledged: bool | None = None, start_time: str | None = None,
    end_time: str | None = None, page: int = 1, page_size: int = 100,
) -> dict[str, Any]:
    if page < 1 or not 1 <= page_size <= MAX_PAGE_SIZE:
        raise APMError("invalid_request", f"page must be positive and page_size must be 1-{MAX_PAGE_SIZE}.")
    normalized_severity = severity.strip().lower() if severity else None
    if normalized_severity and normalized_severity not in ALARM_SEVERITIES:
        raise APMError("invalid_request", "severity must be critical, warning, clear, down, or up.")
    if sum(value is not None for value in (resource_id, monitor_name, monitor_group)) > 1:
        raise APMError("invalid_request", "resource_id, monitor_name, and monitor_group are mutually exclusive upstream filters.")
    return await _query_alarm_page(
        client, severity=normalized_severity, resource_id=resource_id,
        monitor_name=monitor_name, monitor_group=monitor_group,
        acknowledged=acknowledged, start_time=start_time, end_time=end_time,
        page=page, page_size=page_size,
    )


async def _query_alarm_page(
    client: APMClient, *, severity: str | None = None, resource_id: str | None = None,
    attribute_id: str | None = None, monitor_name: str | None = None,
    monitor_group: str | None = None, acknowledged: bool | None = None,
    start_time: str | None = None, end_time: str | None = None,
    page: int = 1, page_size: int = MAX_PAGE_SIZE,
) -> dict[str, Any]:
    params: dict[str, Any] = {
        "view": "Extended", "severity": severity.title() if severity else None,
        "resourceId": resource_id, "monitorName": monitor_name, "monitorGroup": monitor_group,
        "acknowledged": str(acknowledged).lower() if acknowledged is not None else None,
        "startTime": start_time, "endTime": end_time, "page": page, "rows": page_size,
    }
    if attribute_id is not None:
        params["attributeId"] = attribute_id
    payload = await client.get_json("/api/v3/alarms", params)
    raw = _alarm_rows(payload)
    alarms = [normalize_alarm(item) for item in raw]
    meta = payload.get("meta") if isinstance(payload.get("meta"), dict) else {}
    total = _integer(meta.get("total"))
    upstream_page = _integer(meta.get("page")) or page
    records_count = _integer(meta.get("records"))
    if total is not None:
        has_more = upstream_page * page_size < total
    elif records_count is not None:
        has_more = records_count >= page_size
    else:
        has_more = len(raw) >= page_size
    return {"alarms": alarms[:page_size], "page": upstream_page, "page_size": page_size, "has_more": has_more}


async def get_alarm_details(
    client: APMClient, alarm_id: str | None = None, resource_id: str | None = None,
    attribute_id: str | None = None, created_at: str | None = None,
) -> dict[str, Any]:
    if not any((alarm_id, resource_id, attribute_id, created_at)):
        raise APMError("invalid_request", "Provide alarm_id, resource_id, attribute_id, or created_at.")
    matches: list[dict[str, Any]] = []
    page = 1
    while page <= MAX_DETAIL_PAGES:
        result = await _query_alarm_page(
            client, resource_id=resource_id, attribute_id=attribute_id,
            page=page, page_size=MAX_PAGE_SIZE,
        )
        page_matches = result["alarms"]
        if alarm_id is not None:
            page_matches = [item for item in page_matches if item["alarm_id"] is not None and str(item["alarm_id"]) == alarm_id]
        if resource_id is not None:
            page_matches = [item for item in page_matches if item["resource_id"] is not None and str(item["resource_id"]) == resource_id]
        if attribute_id is not None:
            page_matches = [item for item in page_matches if item["attribute_id"] is not None and str(item["attribute_id"]) == attribute_id]
        if created_at is not None:
            page_matches = [item for item in page_matches if item["created_at"] == created_at]
        matches.extend(page_matches)
        if len(matches) > 1:
            raise APMError("ambiguous_alarm", "Multiple alarms match the supplied identifiers.")
        if not result["has_more"]:
            break
        page += 1
    else:
        raise APMError("unsupported_response", "Alarm pagination exceeded the safe query limit.")
    if not matches:
        raise APMError("not_found", "The requested alarm was not found.")
    alarm = matches[0]
    resource = {
        "resource_id": alarm["resource_id"], "display_name": alarm["resource_name"],
        "monitor_type": alarm["monitor_type"], "host": None,
    }
    partial_errors: list[dict[str, str]] = []
    if alarm["resource_id"]:
        try:
            monitor = await _get_monitor(client, str(alarm["resource_id"]))
            resource.update({
                "display_name": monitor["display_name"] or resource["display_name"],
                "monitor_type": monitor["monitor_type"] or resource["monitor_type"],
                "host": monitor["ip_address"],
            })
        except APMError as exc:
            if exc.code in FAIL_CLOSED_ERRORS:
                raise
            partial_errors.append({"source": "ListMonitor", "code": exc.code, "message": exc.message})
    return {"alarm": alarm, "resource": resource, "partial_errors": partial_errors}


async def _get_monitor(client: APMClient, resource_id: str) -> dict[str, Any]:
    try:
        payload = await client.get_json("/AppManager/json/ListMonitor", {"resourceid": resource_id})
        rows = records(payload, ("monitor", "result"))
    except APMError as exc:
        if exc.code not in {"invalid_request", "not_found", "unsupported_response"}:
            raise
        payload = await client.get_json("/AppManager/json/ListMonitor", {"type": "all"})
        rows = records(payload, ("monitor", "result"))
    monitors = [normalize_monitor(row) for row in rows]
    exact = [item for item in monitors if str(item["resource_id"]) == resource_id]
    if not exact:
        raise APMError("not_found", "The requested monitor was not found.")
    if len(exact) > 1:
        raise APMError("ambiguous_resource", "Multiple monitors match the supplied resource ID.")
    return exact[0]


def _integer(value: Any) -> int | None:
    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None

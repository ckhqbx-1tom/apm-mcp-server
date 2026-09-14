from __future__ import annotations

from datetime import datetime
import re
from typing import Any

from ..client import APMClient
from ..errors import APMError
from ..normalization.apm import normalize_monitor_data, normalize_show_polled_data


ALLOWED_PERIODS = {"0", "3", "6", "1", "-7", "12", "7", "2", "-30", "11", "9", "8", "5", "20", "4"}
CUSTOM_TIME_FORMAT = "%Y-%m-%d %H:%M"
CUSTOM_TIME_PATTERN = re.compile(r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}\Z")


def _validate_historical_range(
    period: str | None, start_time: str | None, end_time: str | None,
) -> str | None:
    has_start = start_time is not None
    has_end = end_time is not None
    if has_start != has_end:
        raise APMError("invalid_request", "start_time and end_time must be provided together.")

    if has_start:
        effective_period = period if period is not None else "4"
        if effective_period != "4":
            raise APMError("invalid_request", "Custom start_time/end_time ranges require period=4.")
        parsed_times: list[datetime] = []
        for name, value in (("start_time", start_time), ("end_time", end_time)):
            try:
                if not CUSTOM_TIME_PATTERN.fullmatch(value or ""):
                    raise ValueError
                parsed_times.append(datetime.strptime(value or "", CUSTOM_TIME_FORMAT))
            except ValueError as exc:
                raise APMError(
                    "invalid_request", f"{name} must use the format YYYY-MM-DD HH:MM.",
                ) from exc
        if parsed_times[0] > parsed_times[1]:
            raise APMError("invalid_request", "start_time must not be later than end_time.")
        return effective_period

    if period is not None and period not in ALLOWED_PERIODS:
        raise APMError("invalid_request", "period is not supported by Applications Manager ShowPolledData.")
    return period


async def get_performance_metrics(
    client: APMClient, resource_id: str, attribute_id: str | None = None,
    start_time: str | None = None, end_time: str | None = None, period: str | None = None,
) -> dict[str, Any]:
    if not resource_id.strip():
        raise APMError("invalid_request", "resource_id must not be empty.")
    historical = any(value is not None for value in (start_time, end_time, period))
    if historical:
        if not attribute_id:
            raise APMError("invalid_request", "attribute_id is required for historical metrics.")
        effective_period = _validate_historical_range(period, start_time, end_time)
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

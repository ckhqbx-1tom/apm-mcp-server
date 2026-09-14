from __future__ import annotations

import logging
import sys
from typing import Any, Awaitable, Callable

from mcp.server.fastmcp import FastMCP

from .client import APMClient
from .config import Settings
from .errors import APMError, redact
from .tools import get_alarm_details, get_alarms, get_monitor_summary, get_performance_metrics, search_monitors


async def _invoke(function: Callable[..., Awaitable[dict[str, Any]]], client: APMClient, **kwargs: Any) -> dict[str, Any]:
    try:
        return redact(await function(client, **kwargs), (client.settings.api_key,))
    except APMError as exc:
        return exc.as_dict()
    except Exception:
        # Never log the exception object: third-party errors may embed the request URL.
        logging.getLogger(__name__).error("Unexpected tool failure; details withheld")
        return APMError("upstream_error", "The operation failed safely.").as_dict()


def build_server(settings: Settings, client: APMClient | None = None) -> FastMCP:
    apm = client or APMClient(settings)
    server = FastMCP("ManageEngine Applications Manager", instructions="Read-only operational monitoring tools.")

    @server.tool(name="GetAlarms", description="Return bounded current or historical Applications Manager alarms.")
    async def alarms(
        severity: str | None = None, resource_id: str | None = None, monitor_name: str | None = None,
        monitor_group: str | None = None, acknowledged: bool | None = None,
        start_time: str | None = None, end_time: str | None = None, page: int = 1, page_size: int = 100,
    ) -> dict[str, Any]:
        return await _invoke(get_alarms, apm, severity=severity, resource_id=resource_id, monitor_name=monitor_name,
                             monitor_group=monitor_group, acknowledged=acknowledged, start_time=start_time,
                             end_time=end_time, page=page, page_size=page_size)

    @server.tool(name="GetAlarmDetails", description="Return alarm context and safely resolved resource information.")
    async def alarm_details(alarm_id: str | None = None, resource_id: str | None = None, attribute_id: str | None = None) -> dict[str, Any]:
        return await _invoke(get_alarm_details, apm, alarm_id=alarm_id, resource_id=resource_id, attribute_id=attribute_id)

    @server.tool(name="SearchMonitors", description="Resolve a name, IP address, or application term to monitored resources.")
    async def monitor_search(query: str, search_by: str = "all", limit: int = 50) -> dict[str, Any]:
        return await _invoke(search_monitors, apm, query=query, search_by=search_by, limit=limit)

    @server.tool(name="GetMonitorSummary", description="Return a consolidated health, host, and current-data view of a monitor.")
    async def monitor_summary(resource_id: str) -> dict[str, Any]:
        return await _invoke(get_monitor_summary, apm, resource_id=resource_id)

    @server.tool(name="GetPerformanceMetrics", description="Return bounded current or historical metrics while preserving attribute IDs.")
    async def performance_metrics(
        resource_id: str, attribute_id: str | None = None, start_time: str | None = None,
        end_time: str | None = None, period: str | None = None,
    ) -> dict[str, Any]:
        return await _invoke(get_performance_metrics, apm, resource_id=resource_id, attribute_id=attribute_id,
                             start_time=start_time, end_time=end_time, period=period)
    return server


def main() -> None:
    try:
        settings = Settings.from_env()
        logging.basicConfig(level=settings.log_level, stream=sys.stderr)
        # httpx/httpcore log full request URLs, including query authentication.
        logging.getLogger("httpx").setLevel(logging.CRITICAL)
        logging.getLogger("httpcore").setLevel(logging.CRITICAL)
        if not settings.verify_tls:
            logging.warning("TLS verification is explicitly disabled by APM_VERIFY_TLS")
        build_server(settings).run(transport="stdio")
    except APMError as exc:
        print(f"Configuration failed: {exc}", file=sys.stderr)
        raise SystemExit(2) from None


if __name__ == "__main__":
    main()

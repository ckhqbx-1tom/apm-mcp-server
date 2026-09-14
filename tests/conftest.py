from __future__ import annotations

from typing import Any

import pytest

from apm_mcp.errors import APMError


class FakeClient:
    def __init__(self, responses: dict[str, Any]):
        self.responses = responses
        self.calls: list[tuple[str, dict[str, Any] | None]] = []

    async def get_json(self, path: str, params: dict[str, Any] | None = None) -> Any:
        self.calls.append((path, params))
        value = self.responses.get(path, APMError("upstream_error", "missing fixture"))
        if isinstance(value, Exception):
            raise value
        return value

    async def get_xml(self, path: str, params: dict[str, Any] | None = None) -> Any:
        return await self.get_json(path, params)


@pytest.fixture
def alarm_payload():
    return {"alarms": [{
        "alarmId": "a1", "resourceId": "10", "displayName": "payments",
        "monitorType": "REST API", "severity": "critical", "message": "slow",
        "attributeId": "7", "attributeName": "Response Time", "acknowledged": "false",
        "alertCreationTime": 1700000000000,
    }]}


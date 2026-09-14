from __future__ import annotations

from typing import Any
import json
from pathlib import Path

import pytest

from apm_mcp.errors import APMError

FIXTURES = Path(__file__).parent / "fixtures"


def load_json(name: str) -> Any:
    return json.loads((FIXTURES / name).read_text())


def load_text(name: str) -> str:
    return (FIXTURES / name).read_text()


class FakeClient:
    def __init__(self, responses: dict[str, Any]):
        self.responses = responses
        self.calls: list[tuple[str, dict[str, Any] | None]] = []

    async def get_json(self, path: str, params: dict[str, Any] | None = None) -> Any:
        self.calls.append((path, params))
        value = self.responses.get(path, APMError("upstream_error", "missing fixture"))
        if isinstance(value, ResponseSequence):
            value = value.values.pop(0)
        if isinstance(value, Exception):
            raise value
        return value

    async def get_xml(self, path: str, params: dict[str, Any] | None = None) -> Any:
        return await self.get_json(path, params)


class ResponseSequence:
    def __init__(self, *values: Any):
        self.values = list(values)


@pytest.fixture
def alarm_payload():
    return {"alarms": [{
        "alarmId": "a1", "resourceId": "10", "displayName": "payments",
        "monitorType": "REST API", "severity": "critical", "message": "slow",
        "attributeId": "7", "attributeName": "Response Time", "acknowledged": "false",
        "alertCreationTime": 1700000000000,
    }]}

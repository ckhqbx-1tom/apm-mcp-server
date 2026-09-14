import pytest

from apm_mcp.tools.notes import get_alarm_notes
from conftest import FakeClient, load_json


@pytest.mark.asyncio
async def test_official_alarm_annotations_shape_and_identity():
    client = FakeClient({"/AppManager/json/AlarmAction": load_json("alarm_annotations.json")})
    result = await get_alarm_notes(client, "10000035", "1651")
    assert client.calls[-1] == ("/AppManager/json/AlarmAction", {
        "action": "ListAnnotations", "entity": "10000035_1651",
    })
    assert result["alarm"] == {"resource_id": "10000035", "attribute_id": "1651"}
    assert result["notes"][0]["text"] == "Investigating the incident."
    assert result["notes"][0]["author"] == "operator"


@pytest.mark.asyncio
async def test_no_annotations_message_is_not_a_note():
    payload = {"response-code": "4000", "response": {"result": [{"message": "No annotations."}]}}
    result = await get_alarm_notes(FakeClient({"/AppManager/json/AlarmAction": payload}), "1", "2")
    assert result["notes"] == []

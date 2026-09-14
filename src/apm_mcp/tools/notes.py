from __future__ import annotations

from typing import Any

from ..client import APMClient
from ..errors import APMError
from ..normalization.apm import field, normalize_timestamp
from .inventory import _items


async def get_alarm_notes(client: APMClient, resource_id: str, attribute_id: str) -> dict[str, Any]:
    if not resource_id.strip() or not attribute_id.strip():
        raise APMError("invalid_request", "resource_id and attribute_id are required.")
    payload = await client.post_json("/AppManager/json/AlarmAction", {
        "action": "ListAnnotations", "entity": f"{resource_id}_{attribute_id}",
    })
    if not isinstance(payload, dict) or not isinstance(payload.get("response"), dict):
        raise APMError("unsupported_response", "Applications Manager returned an unsupported annotation response.")
    result = payload["response"].get("result")
    if not isinstance(result, list):
        raise APMError("parse_error", "Applications Manager annotation result is malformed.")
    rows: list[dict[str, Any]] = []
    for item in result:
        if not isinstance(item, dict):
            raise APMError("parse_error", "Applications Manager annotation is malformed.")
        nested = field(item, "Annotations", "Annotation", "notes")
        rows.extend(_items(nested) if nested is not None else [item])
    notes = []
    for item in rows[:500]:
        text = field(item, "annotation", "note", "text", "message")
        has_annotation_shape = any(field(item, name) is not None for name in (
            "annotation", "note", "text", "username", "user", "author", "technician",
            "createdTime", "LongTime", "ModTime", "annotationTime",
        ))
        if text is None or not has_annotation_shape:
            continue
        notes.append({"text": text, "author": field(item, "username", "user", "author", "technician"),
                      "created_at": normalize_timestamp(field(item, "createdTime", "LongTime", "ModTime", "time", "timestamp", "annotationTime"))})
    return {"alarm": {"resource_id": resource_id, "attribute_id": attribute_id}, "notes": notes}

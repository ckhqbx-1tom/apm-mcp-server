from pydantic import BaseModel


class Alarm(BaseModel):
    alarm_id: str | None = None
    resource_id: str | None = None
    resource_name: str | None = None
    monitor_type: str | None = None
    parent_resource_id: str | None = None
    severity: str | None = None
    severity_code: str | int | None = None
    message: str | None = None
    attribute_id: str | None = None
    attribute_name: str | None = None
    acknowledged: bool | None = None
    created_at: str | None = None
    modified_at: str | None = None
    latest_note: str | None = None

from pydantic import BaseModel


class Monitor(BaseModel):
    resource_id: str | None = None
    display_name: str | None = None
    monitor_type: str | None = None
    health: str | None = None
    availability: str | None = None
    health_message: str | None = None
    availability_message: str | None = None
    ip_address: str | None = None
    managed: bool | None = None


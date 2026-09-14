from pydantic import BaseModel, Field


class Metric(BaseModel):
    attribute_id: str | None = None
    name: str | None = None
    unit: str | None = None
    current_value: float | None = None
    samples: list[dict[str, str | float | None]] = Field(default_factory=list)
    summary: dict[str, float | None] = Field(
        default_factory=lambda: {"min": None, "max": None, "avg": None}
    )

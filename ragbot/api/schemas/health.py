"""Health check schemas."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class ComponentHealth(BaseModel):
    """Health information for a specific subsystem."""

    status: str = Field(description="Subsystem status: healthy, degraded, unhealthy, missing")
    error: str | None = Field(default=None, description="Error detail if degraded or unhealthy")
    note: str | None = Field(default=None, description="Diagnostic note")


class HealthResponse(BaseModel):
    """Overall application and service health response."""

    status: str = Field(description="Overall health status: healthy, degraded, unhealthy")
    timestamp: float = Field(description="Health check execution timestamp")
    components: dict[str, Any] = Field(
        default_factory=dict, description="Detailed component health breakdown"
    )
    issues: list[str] = Field(
        default_factory=list, description="List of detected health issues"
    )

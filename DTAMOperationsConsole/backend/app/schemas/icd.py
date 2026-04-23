"""Request and response schemas for ICD message send actions."""

from typing import Any

from pydantic import BaseModel, Field


class IcdSendRequest(BaseModel):
    payload: dict[str, Any] = Field(..., description="DTAM ICD payload to validate and send.")
    target_ip: str | None = Field(None, description="Optional UDP target IP override.")
    target_port: int | None = Field(None, ge=1, le=65535, description="Optional UDP target port override.")


class IcdSendResponse(BaseModel):
    message_id: str
    protocol: str
    sent: bool
    bytes_sent: int
    target: str | None
    errors: list[str]
    payload: dict[str, Any]

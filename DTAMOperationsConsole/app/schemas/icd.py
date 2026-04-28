"""Request and response schemas for ICD message send actions."""

from typing import Any

from pydantic import BaseModel, Field


class IcdSendRequest(BaseModel):
    payload: dict[str, Any] = Field(..., description="DTAM ICD payload to validate and send.")
    target_ip: str | None = Field(
        None,
        description="Optional DTAM State Server host override (e.g. cloud deployment IP).",
    )


class IcdSendResponse(BaseModel):
    message_id: str
    protocol: str
    sent: bool
    bytes_sent: int
    target: str | None
    errors: list[str]
    payload: dict[str, Any]

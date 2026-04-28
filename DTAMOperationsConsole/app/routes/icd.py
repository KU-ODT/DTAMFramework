"""API routes for sending DTAM ICD messages."""

from fastapi import APIRouter

from app.schemas.icd import IcdSendRequest, IcdSendResponse
from app.comm import send_icd_command

router = APIRouter()


@router.post("/{message_id}/send", response_model=IcdSendResponse)
async def send_icd_message(message_id: str, request: IcdSendRequest) -> IcdSendResponse:
    return send_icd_command(
        message_id,
        request.payload,
        target_ip=request.target_ip,
    )

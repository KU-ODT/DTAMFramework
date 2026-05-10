"""API routes for sending DTAM ICD messages."""

from fastapi import APIRouter

from backend.app.schemas.icd import IcdSendRequest, IcdSendResponse
from backend.app.services.dtam_sdk_service import send_dtam_message

router = APIRouter()


@router.post("/{message_id}/send", response_model=IcdSendResponse)
async def send_icd_message(message_id: str, request: IcdSendRequest) -> IcdSendResponse:
    return send_dtam_message(
        message_id,
        request.payload,
        target_ip=request.target_ip,
    )

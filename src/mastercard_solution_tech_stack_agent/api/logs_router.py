from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from src.mastercard_solution_tech_stack_agent.config.db_setup import get_db
from src.mastercard_solution_tech_stack_agent.database.schemas import (
    ChatLog,
    ConversationHistory,
)

router = APIRouter(
    responses={
        200: {"description": "Success - Request was successful."},
        201: {"description": "Created - Resource was successfully created."},
        400: {
            "description": "Bad Request - The request could not be understood or was missing required parameters."
        },
        401: {
            "description": "Unauthorized - Authentication is required and has failed or not yet been provided."
        },
        403: {
            "description": "Forbidden - The request was valid, but you do not have the necessary permissions."
        },
        404: {"description": "Not Found - The requested resource could not be found."},
        409: {
            "description": "Conflict - The request could not be completed due to a conflict with the current state of the resource."
        },
        422: {
            "description": "Unprocessable Entity - The request was well-formed but could not be followed due to validation errors."
        },
        500: {
            "description": "Internal Server Error - An unexpected server error occurred."
        },
    },
)


@router.get("/chat", summary="Get recent chat logs", response_model=List[dict])
def get_chat_logs(
    room_id: Optional[str] = None,
    limit: int = Query(
        50, le=100, description="Max number of logs to return (max 100)"
    ),
    db: Session = Depends(get_db),
):
    query = db.query(ChatLog)
    if room_id:
        query = query.filter(ChatLog.room_id == room_id)
    query = query.order_by(ChatLog.timestamp.desc()).limit(limit)
    logs = query.all()
    return [log.to_dict() for log in logs]


@router.get(
    "/history", summary="Get past conversation history", response_model=List[dict]
)
def get_conversation_history_logs(
    room_id: str,
    db: Session = Depends(get_db),
):
    if not room_id:
        raise HTTPException(status_code=400, detail="room_id is required")

    logs = (
        db.query(ConversationHistory)
        .filter(ConversationHistory.room_id == room_id)
        .order_by(ConversationHistory.created_at.asc())
        .all()
    )
    return [entry.to_dict() for entry in logs]

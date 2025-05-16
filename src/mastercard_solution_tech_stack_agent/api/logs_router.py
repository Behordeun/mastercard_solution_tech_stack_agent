from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from src.mastercard_solution_tech_stack_agent.database.pd_db import DatabaseSession
from src.mastercard_solution_tech_stack_agent.database.schemas import (
    ChatLog,
    ConversationHistory,
)

router = APIRouter(prefix="/logs", tags=["Chat Logs"])


# Dependency to get DB session
def get_db():
    db = DatabaseSession()
    try:
        yield db
    finally:
        db.close()


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

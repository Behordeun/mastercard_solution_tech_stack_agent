import os
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from src.mastercard_solution_tech_stack_agent.database.pd_db import DatabaseSession
from src.mastercard_solution_tech_stack_agent.database.schemas import (
    ChatLog,
    ConversationHistory,
)
from src.mastercard_solution_tech_stack_agent.error_trace.errorlogger import system_logger


# === Log directory setup ===
LOG_DIR = "src/mastercard_solution_tech_stack_agent/logs"
os.makedirs(LOG_DIR, exist_ok=True)  # Ensure the logs directory exists

# === Log file paths ===
LOG_FILES = {
    "info": os.path.join(LOG_DIR, "info.log"),
    "warning": os.path.join(LOG_DIR, "warning.log"),
    "error": os.path.join(LOG_DIR, "error.log"),
}


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
    session_id: Optional[str] = None,
    limit: int = Query(
        50, le=100, description="Max number of logs to return (max 100)"
    ),
    db: Session = Depends(get_db),
):
    system_logger.info("Received request to get chat logs")
    query = db.query(ChatLog)
    if session_id:
        query = query.filter(ChatLog.session_id == session_id)
    query = query.order_by(ChatLog.timestamp.desc()).limit(limit)
    logs = query.all()
    if not logs:
        raise HTTPException(status_code=404, detail="No chat logs found")
    system_logger.info(f"Found {len(logs)} chat logs")
    return [log.to_dict() for log in logs]


@router.get(
    "/history", summary="Get past conversation history", response_model=List[dict]
)
def get_conversation_history_logs(
    session_id: str,
    db: Session = Depends(get_db),
):
    system_logger.info("Received request to get conversation history logs")
    if not session_id:
        raise HTTPException(status_code=400, detail="session_id is required")

    logs = (
        db.query(ConversationHistory)
        .filter(ConversationHistory.session_id == session_id)
        .order_by(ConversationHistory.created_at.asc())
        .all()
    )
    if not logs:
        raise HTTPException(status_code=404, detail="No conversation history found")
    system_logger.info(f"Found {len(logs)} conversation history logs")
    return [entry.to_dict() for entry in logs]

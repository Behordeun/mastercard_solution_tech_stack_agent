from datetime import datetime
from typing import Any, Dict, Optional

from pydantic import BaseModel
from sqlalchemy import Column, DateTime, Integer, String, Text, func
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.types import JSON

from src.config.db_setup import engine

Base = declarative_base()


class AIMessageResponse(BaseModel):
    content: str
    id: Optional[str] = None
    usage_metadata: Optional[Dict[str, Any]] = None
    response_metadata: Optional[Dict[str, Any]] = None
    additional_kwargs: Optional[Dict[str, Any]] = None


class ConversationHistory(Base):
    __tablename__ = "conversation_history"

    id = Column(Integer, primary_key=True)
    room_id = Column(String, index=True)
    ai_message = Column(Text)
    user_message = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)


class ChatLog(Base):
    __tablename__ = "chat_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    room_id = Column(String(100), nullable=False)
    user_message = Column(Text, nullable=True)
    ai_response = Column(Text, nullable=True)
    system_note = Column(Text, nullable=True)
    resource_urls = Column(Text, nullable=True)
    timestamp = Column(DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<ChatLog id={self.id} room={self.room_id} time={self.timestamp}>"


class AgentSession(Base):
    __tablename__ = "agent_sessions"

    room_id = Column(String, primary_key=True)
    project_context = Column(JSON, default={})
    asked_questions = Column(JSON, default=[])
    updated_at = Column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


# ✅ Only run in dev, not in production!
Base.metadata.create_all(bind=engine)

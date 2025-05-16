from datetime import datetime
from sqlalchemy import Column, DateTime, Integer, String, Text, func, ForeignKey, JSON
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from sqlalchemy.types import JSON

Base = declarative_base()

class UserSession(Base):
    __tablename__ = "user_sessions"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(String, nullable=False, unique=True)
    user_id = Column(String)
    conversation_summary = Column(String)
    recommended_stack = Column(JSON)

    conversation_history = relationship(
        "ConversationHistory", back_populates="user_session")

class ConversationHistory(Base):
    __tablename__ = "conversation_history"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(String, ForeignKey("user_sessions.session_id"), nullable=False)
    user_id = Column(String, nullable=False)
    user_message = Column(String)
    ai_message = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)

    user_session = relationship("UserSession", back_populates="conversation_history")

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
# Base.metadata.create_all(bind=engine)

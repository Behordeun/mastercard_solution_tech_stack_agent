from datetime import datetime, timezone

from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship

Base = declarative_base()


class UserSession(Base):
    __tablename__ = "user_sessions"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(String, nullable=False, unique=True)
    user_id = Column(String)
    conversation_summary = Column(String)
    recommended_stack = Column(JSON)

    conversation_history = relationship(
        "ConversationHistory", back_populates="user_session"
    )


class ConversationHistory(Base):
    __tablename__ = "conversation_history"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(String, ForeignKey("user_sessions.session_id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    user_message = Column(String)
    ai_message = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)

    user_session = relationship("UserSession", back_populates="conversation_history")
    user = relationship("User", back_populates="conversation_histories")


class ChatLog(Base):
    __tablename__ = "chat_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(String(100), nullable=False)

    user_id = Column(
        Integer, ForeignKey("users.id"), nullable=False
    )  # 👈 ADD THIS LINE

    user_message = Column(Text, nullable=True)
    ai_response = Column(Text, nullable=True)
    system_note = Column(Text, nullable=True)
    resource_urls = Column(Text, nullable=True)
    timestamp = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="chat_logs")  # 👈 ADD THIS LINE

    def __repr__(self):
        return f"<ChatLog id={self.id} room={self.session_id} time={self.timestamp}>"


class AgentSession(Base):
    __tablename__ = "agent_sessions"

    session_id = Column(String, primary_key=True)
    project_context = Column(JSON, default={})
    asked_questions = Column(JSON, default=[])
    updated_at = Column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class AIMessageResponse(Base):
    __tablename__ = "ai_message_responses"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"))
    profile_id = Column(Integer, ForeignKey("user_profiles.id", ondelete="CASCADE"))
    message = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="ai_message_responses")
    profile = relationship("UserProfile", back_populates="ai_message_responses")


# === Users ===
class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    hashed_password = Column(String(255), nullable=False)
    first_name = Column(String(100), nullable=False)
    last_name = Column(String(100), nullable=False)

    is_active = Column(Boolean, default=True)
    is_verified = Column(Boolean, default=False)
    is_deleted = Column(Boolean, default=False)
    is_admin = Column(Boolean, default=False)
    is_super_admin = Column(Boolean, default=False)

    created_at = Column(
        DateTime(timezone=True), default=datetime.now(timezone.utc), nullable=False
    )
    updated_at = Column(
        DateTime(timezone=True),
        default=datetime.now(timezone.utc),
        onupdate=datetime.now(timezone.utc),
        nullable=False,
    )

    # Relationships
    profiles = relationship(
        "UserProfile", back_populates="user", cascade="all, delete-orphan"
    )
    conversation_histories = relationship(
        "ConversationHistory", back_populates="user", cascade="all, delete-orphan"
    )
    chat_logs = relationship(
        "ChatLog", back_populates="user", cascade="all, delete-orphan"
    )
    ai_message_responses = relationship(
        "AIMessageResponse", back_populates="user", cascade="all, delete-orphan"
    )


# === User Profiles ===
class UserProfile(Base):
    __tablename__ = "user_profiles"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )

    profile_picture_url = Column(String, nullable=True)

    otp = Column(String(6), nullable=True)
    otp_created_at = Column(DateTime(timezone=True), nullable=True)

    created_at = Column(DateTime(timezone=True), default=func.now(), nullable=False)
    updated_at = Column(
        DateTime(timezone=True), default=func.now(), onupdate=func.now(), nullable=False
    )

    # Relationships
    user = relationship("User", back_populates="profiles")
    ai_message_responses = relationship(
        "AIMessageResponse", back_populates="profile", cascade="all, delete-orphan"
    )


# === Admins ===
class Admin(Base):
    __tablename__ = "admins"

    id = Column(Integer, primary_key=True, autoincrement=True)
    email = Column(String(255), unique=True, nullable=False)
    password = Column(String(255), nullable=False)
    is_superuser = Column(Boolean, default=False)

    created_at = Column(DateTime(timezone=True), default=datetime.now(timezone.utc))
    updated_at = Column(
        DateTime(timezone=True),
        default=datetime.now(timezone.utc),
        onupdate=datetime.now(timezone.utc),
    )


# ✅ Only run in dev, not in production!
# Base.metadata.create_all(bind=engine)

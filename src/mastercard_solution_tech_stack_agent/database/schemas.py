from datetime import datetime, timezone

from sqlalchemy import Boolean, Column, DateTime
from sqlalchemy import Enum as SQLAlchemyEnum
from sqlalchemy import ForeignKey, Integer, String, Text, func
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from sqlalchemy.types import JSON

Base = declarative_base()

# === AI Responses ===


class AIMessageResponse(Base):
    __tablename__ = "ai_message_responses"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    profile_id = Column(
        Integer, ForeignKey("user_profiles.id", ondelete="CASCADE"), nullable=True
    )

    content = Column(Text, nullable=False)
    usage_metadata = Column(JSON, nullable=True)
    response_metadata = Column(JSON, nullable=True)
    additional_kwargs = Column(JSON, nullable=True)

    created_at = Column(
        DateTime(timezone=True), default=datetime.now(timezone.utc), nullable=False
    )

    # Relationships
    user = relationship("User", back_populates="ai_message_responses")
    profile = relationship("UserProfile", back_populates="ai_message_responses")


# === Conversation History ===


class ConversationHistory(Base):
    __tablename__ = "conversation_history"

    id = Column(Integer, primary_key=True, autoincrement=True)
    room_id = Column(Integer, index=True, nullable=False)
    user_id = Column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )

    ai_message = Column(Text)
    user_message = Column(Text)
    created_at = Column(
        DateTime(timezone=True), default=datetime.now(timezone.utc), nullable=False
    )

    # Relationships
    user = relationship("User", back_populates="conversation_histories")


# === Chat Logs ===
class ChatLog(Base):
    __tablename__ = "chat_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    room_id = Column(Integer, nullable=False)
    user_id = Column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )

    user_message = Column(Text, nullable=True)
    ai_response = Column(Text, nullable=True)
    system_note = Column(Text, nullable=True)
    resource_urls = Column(Text, nullable=True)

    timestamp = Column(
        DateTime(timezone=True), default=datetime.now(timezone.utc), nullable=False
    )

    # Relationships
    user = relationship("User", back_populates="chat_logs")


# === Agent Sessions ===
class AgentSession(Base):
    __tablename__ = "agent_sessions"

    room_id = Column(Integer, primary_key=True)
    project_context = Column(JSON, default=dict)
    asked_questions = Column(JSON, default=list)
    updated_at = Column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


# === Users ===
class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String(255), unique=True, nullable=False, index=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    hashed_password = Column(String(255), nullable=False)
    first_name = Column(String(100), nullable=False)
    last_name = Column(String(100), nullable=False)

    is_active = Column(Boolean, default=True)
    is_verified = Column(Boolean, default=False)
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

    profile_picture = Column(String, nullable=True)
    bio = Column(Text, nullable=True)
    linkedin = Column(String(255), nullable=True)
    twitter = Column(String(255), nullable=True)
    nationality = Column(String(100), nullable=True)
    phone_number = Column(String(20), nullable=True)

    gender = Column(
        SQLAlchemyEnum("Male", "Female", "Other", name="gender_types"), nullable=True
    )

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

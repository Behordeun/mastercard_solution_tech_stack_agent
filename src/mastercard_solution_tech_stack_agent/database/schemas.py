from datetime import datetime, timezone

from sqlalchemy import Boolean, Column, DateTime
from sqlalchemy import Enum as SQLAlchemyEnum
from sqlalchemy import ForeignKey, Integer, String, Text, func
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from sqlalchemy.types import JSON

Base = declarative_base()


class AIMessageResponse(Base):
    __tablename__ = "ai_message_responses"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )  # Link to User
    profile_id = Column(
        Integer, ForeignKey("user_profiles.id", ondelete="CASCADE"), nullable=True
    )  # Optional link to UserProfile
    content = Column(Text, nullable=False)
    usage_metadata = Column(JSON, nullable=True)
    response_metadata = Column(JSON, nullable=True)
    additional_kwargs = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.now(timezone.utc), nullable=False)

    # Relationships
    user = relationship("User", back_populates="ai_message_responses")
    profile = relationship("UserProfile", back_populates="ai_message_responses")


class ConversationHistory(Base):
    __tablename__ = "conversation_history"

    id = Column(Integer, primary_key=True)
    room_id = Column(String, index=True)
    user_id = Column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )  # Link to User
    ai_message = Column(Text)
    user_message = Column(Text)
    created_at = Column(DateTime, default=datetime.now(timezone.utc), nullable=False)

    # Relationships
    user = relationship("User", back_populates="conversation_histories")


class ChatLog(Base):
    __tablename__ = "chat_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    room_id = Column(String(100), nullable=False)
    user_id = Column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )  # Link to User
    user_message = Column(Text, nullable=True)
    ai_response = Column(Text, nullable=True)
    system_note = Column(Text, nullable=True)
    resource_urls = Column(Text, nullable=True)
    timestamp = Column(DateTime, default=datetime.now(timezone.utc), nullable=False)

    # Relationships
    user = relationship("User", back_populates="chat_logs")


class AgentSession(Base):
    __tablename__ = "agent_sessions"

    room_id = Column(String, primary_key=True)
    project_context = Column(JSON, default={})
    asked_questions = Column(JSON, default=[])
    updated_at = Column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


# Update User and UserProfile to include relationships
class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String(255), unique=True, nullable=False, index=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    hashed_password = Column(String(255), nullable=False)
    first_name = Column(String(100), nullable=False)  # Add this field
    last_name = Column(String(100), nullable=False)  # Add this field
    is_active = Column(Boolean, default=True)
    is_verified = Column(Boolean, default=False)
    is_admin = Column(Boolean, default=False)
    is_super_admin = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.now(timezone.utc), nullable=False)
    updated_at = Column(
        DateTime,
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


class UserProfile(Base):
    __tablename__ = "user_profiles"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    profile_picture = Column(String, nullable=True)
    first_name = Column(String(100), nullable=False)
    last_name = Column(String(100), nullable=False)
    bio = Column(Text, nullable=True)
    linkedin = Column(String(255), nullable=True)
    twitter = Column(String(255), nullable=True)
    nationality = Column(String(100), nullable=True)
    phone_number = Column(String(20), nullable=True)
    gender = Column(
        SQLAlchemyEnum("Male", "Female", "Other", name="gender_types"), nullable=True
    )
    otp = Column(String(6), nullable=True)  # OTP limited to 6 characters
    otp_created_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime, default=func.now(), nullable=False)
    updated_at = Column(
        DateTime, default=func.now(), onupdate=func.now(), nullable=False
    )

    # Relationships
    user = relationship("User", back_populates="profiles")
    ai_message_responses = relationship(
        "AIMessageResponse", back_populates="profile", cascade="all, delete-orphan"
    )


class Admin(Base):
    __tablename__ = "admins"

    id = Column(Integer, primary_key=True, autoincrement=True)
    email = Column(String(255), unique=True, nullable=False)
    password = Column(String(255), nullable=False)
    is_superuser = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.now(timezone.utc))
    updated_at = Column(
        DateTime,
        default=datetime.now(timezone.utc),
        onupdate=datetime.now(timezone.utc),
    )


# ✅ Only run in dev, not in production!
# Base.metadata.create_all(bind=engine)

import logging
from contextlib import contextmanager
from datetime import datetime
from typing import Generator, Optional

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from src.mastercard_solution_tech_stack_agent.config.db_setup import SessionLocal
from src.mastercard_solution_tech_stack_agent.database.schemas import (
    AgentSession,
    ConversationHistory,
    UserSession,
)
from src.mastercard_solution_tech_stack_agent.error_trace.errorlogger import (
    system_logger,
)

logger = logging.getLogger(__name__)

DatabaseSession = SessionLocal


@contextmanager
def get_db() -> Generator[Session, None, None]:
    """Context manager for SQLAlchemy session."""
    db = DatabaseSession()
    try:
        yield db
    finally:
        db.close()


# ✅ Conversation Insertion
def insert_conversation(db: Session, session_id, ai_message, user_message, user_id):
    """
    Insert a conversation entry into the database with required fields.
    """
    try:
        new_entry = ConversationHistory(
            session_id=session_id,
            user_id=user_id,
            user_message=user_message,
            ai_message=ai_message,
            created_at=datetime.utcnow(),
        )
        db.add(new_entry)
        db.commit()
        db.refresh(new_entry)
        return new_entry
    except SQLAlchemyError as e:
        db.rollback()
        system_logger.error("Error inserting conversation: %s", e, exc_info=True)
        raise "SQLAlchemyError: Failed to insert conversation into the database."


def create_session(db: Session, session_id: str, user_id: str) -> None:
    """
    Create a new session in the database.
    """
    try:
        new_session = UserSession(session_id=session_id, user_id=user_id)
        db.add(new_session)
        db.commit()
        db.refresh(new_session)
    except SQLAlchemyError as e:
        db.rollback()
        system_logger.error(f"Error creating session: {e}", exc_info=True)
        raise


def get_user_session(db: Session, session_id: str) -> Optional[UserSession]:
    """
    Retrieve a user session from the database.
    """
    try:
        return db.query(UserSession).filter_by(session_id=session_id).first()
    except SQLAlchemyError as e:
        system_logger.error("Error fetching user session: %s", e, exc_info=True)
        raise


def save_summary(db: Session, session_id, summary):
    """
    Save a conversation summary to the database.
    """
    try:

        out = (
            db.query(UserSession)
            .filter(UserSession.session_id == session_id)
            .update({UserSession.conversation_summary: summary})
        )
        db.commit()
        # db.refresh(new_entry)
        return out
    except SQLAlchemyError as e:
        db.rollback()
        print(e)
        system_logger.error("Error inserting conversation: %s", str(e), exc_info=True)
        raise


def get_summary(db: Session, session_id: str) -> Optional[str]:
    """
    Retrieve a conversation summary from the database.
    """
    try:
        session = db.query(UserSession).filter_by(session_id=session_id).first()
        if session:
            return session.conversation_summary
        return None
    except SQLAlchemyError as e:
        system_logger.error("Error fetching conversation summary: %s", e, exc_info=True)
        raise


def save_techstack(db: Session, session_id, recommended_stack):
    """
    Save the recommended tech stack to the database.
    """
    try:

        out = (
            db.query(UserSession)
            .filter(UserSession.session_id == session_id)
            .update({UserSession.recommended_stack: recommended_stack})
        )
        db.commit()
        # db.refresh(new_entry)
        return out
    except SQLAlchemyError as e:
        db.rollback()
        system_logger.error(f"Error inserting conversation: {e}", exc_info=True)
        raise


# ✅ Chat History Retrieval
def get_conversation_history(db: Session, session_id: str, k: int = 48) -> str:
    try:
        messages = (
            db.query(ConversationHistory)
            .filter(ConversationHistory.session_id == session_id)
            .order_by(ConversationHistory.created_at.desc())
            .limit(k)
            .all()
        )

        seen_messages = set()
        unique_messages = []
        for msg in reversed(messages):
            combined = f"{msg.user_message or ''} {msg.ai_message or ''}".strip()
            if combined and combined not in seen_messages:
                seen_messages.add(combined)
                unique_messages.append(msg)

        # Format for agent state
        conversation_parts = []
        for msg in unique_messages:
            if msg.user_message:
                user_text = msg.user_message
                conversation_parts.append(
                    {
                        "role": "user",
                        "content": user_text,
                    }
                )
            if msg.ai_message:
                ai_text = msg.ai_message
                conversation_parts.append(
                    {
                        "role": "ai",
                        "content": ai_text,
                    }
                )

        return conversation_parts

    except Exception as e:
        logger.error("Error retrieving chat history: %s", str(e))
        raise


# ✅ Agent Session Retrieval
def get_agent_session(db: Session, session_id: str) -> Optional[AgentSession]:
    try:
        return db.query(AgentSession).filter_by(session_id=session_id).first()
    except Exception as e:
        logger.error("Error fetching agent session: %s", str(e))
        raise


# ✅ Agent Session Save/Update
def save_agent_session(
    db: Session, session_id: str, context: dict, questions: list
) -> None:
    try:
        existing = db.query(AgentSession).filter_by(session_id=session_id).first()
        if existing:
            existing.project_context = context
            existing.asked_questions = questions
        else:
            db.add(
                AgentSession(
                    session_id=session_id,
                    project_context=context,
                    asked_questions=questions,
                )
            )
        db.commit()
    except Exception as e:
        db.rollback()
        logger.error("Error saving agent session: %s", str(e))
        raise

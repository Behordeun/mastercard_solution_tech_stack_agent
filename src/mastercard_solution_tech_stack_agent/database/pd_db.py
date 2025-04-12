import logging
from contextlib import contextmanager
from typing import Generator, Optional

from sqlalchemy.orm import Session

from src.mastercard_solution_tech_stack_agent.config.db_setup import SessionLocal
from src.mastercard_solution_tech_stack_agent.database.schemas import (
    AgentSession,
    ConversationHistory,
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
def insert_conversation(
    db: Session, ai_message: str, room_id: int, user_id: int, user_message: str = ""
):
    """
    Insert a new conversation into the database.

    Args:
        db (Session): SQLAlchemy database session.
        ai_message (str): The AI's initial message.
        room_id (int): The room ID for the conversation.
        user_id (int): The ID of the user associated with the conversation.
        user_message (str): The user's initial message (default: "").

    Returns:
        None
    """
    try:
        new_conversation = ConversationHistory(
            room_id=room_id,
            user_id=user_id,
            ai_message=ai_message,
            user_message=user_message,
        )
        db.add(new_conversation)
        db.commit()
    except Exception as e:
        logger.error(f"Error inserting conversation: {str(e)}")
        raise


# ✅ Chat History Retrieval
def get_conversation_history(
    db: Session, room_id: int, user_id: int, k: int = 48
) -> list:
    """
    Retrieve conversation history for a specific room and user.

    Args:
        db (Session): SQLAlchemy database session.
        room_id (int): The room ID for the conversation.
        user_id (int): The ID of the user requesting the conversation history.
        k (int): The maximum number of messages to retrieve (default: 48).

    Returns:
        list: A list of formatted conversation parts (user and AI messages).
    """
    try:
        # Query messages filtered by room_id and user_id
        messages = (
            db.query(ConversationHistory)
            .filter(
                ConversationHistory.room_id == room_id,
                ConversationHistory.user_id
                == user_id,  # Ensure messages belong to the user
            )
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
        logger.error(f"Error retrieving chat history: {str(e)}")
        raise


# ✅ Agent Session Retrieval
def get_agent_session(db: Session, room_id: int) -> Optional[AgentSession]:
    try:
        return db.query(AgentSession).filter_by(room_id=room_id).first()
    except Exception as e:
        logger.error(f"Error fetching agent session: {str(e)}")
        raise


# ✅ Agent Session Save/Update
def save_agent_session(
    db: Session, room_id: int, context: dict, questions: list
) -> None:
    try:
        existing = db.query(AgentSession).filter_by(room_id=room_id).first()
        if existing:
            existing.project_context = context
            existing.asked_questions = questions
        else:
            db.add(
                AgentSession(
                    room_id=room_id, project_context=context, asked_questions=questions
                )
            )
        db.commit()
    except Exception as e:
        db.rollback()
        logger.error(f"Error saving agent session: {str(e)}")
        raise

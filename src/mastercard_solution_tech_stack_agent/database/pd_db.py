import logging
import os
from contextlib import contextmanager
from typing import Generator, Optional

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from src.mastercard_solution_tech_stack_agent.config.db_setup import engine, SessionLocal
from src.mastercard_solution_tech_stack_agent.database.schemas import AgentSession, ConversationHistory

logger = logging.getLogger(__name__)

# # ✅ Database connection via env
# DATABASE_URL = os.getenv("POSTGRES_DB_URL")
# if not DATABASE_URL:
#     raise ValueError("🚨 ERROR: POSTGRES_DB_URL is not set. Check your .env file.")

# # ✅ SQLAlchemy engine & session
# engine = create_engine(DATABASE_URL, echo=True)
# SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
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
    db: Session, room_id: str, ai_message: str, user_message: str = ""
) -> None:
    try:
        conversation = ConversationHistory(
            room_id=room_id, ai_message=ai_message, user_message=user_message
        )
        db.add(conversation)
        db.commit()

        print("Conversation Added")
    except Exception as e:
        db.rollback()
        logger.error(f"Error inserting chat message: {str(e)}")
        raise


# ✅ Chat History Retrieval
def get_conversation_history(db: Session, room_id: str, k: int = 48) -> str:
    try:
        messages = (
            db.query(ConversationHistory)
            .filter(ConversationHistory.room_id == room_id)
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
                conversation_parts.append({
                    "role": "user",
                    "content": user_text,
                })
            if msg.ai_message:
                ai_text = msg.ai_message
                conversation_parts.append({
                    "role": "ai",
                    "content": ai_text,
                })

        return conversation_parts

    except Exception as e:
        logger.error(f"Error retrieving chat history: {str(e)}")
        raise


# ✅ Agent Session Retrieval
def get_agent_session(db: Session, room_id: str) -> Optional[AgentSession]:
    try:
        return db.query(AgentSession).filter_by(room_id=room_id).first()
    except Exception as e:
        logger.error(f"Error fetching agent session: {str(e)}")
        raise


# ✅ Agent Session Save/Update
def save_agent_session(
    db: Session, room_id: str, context: dict, questions: list
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

import uuid
import logging

from typing import Annotated, Union
from fastapi import APIRouter, Depends, HTTPException
from fastapi.encoders import jsonable_encoder

from sqlalchemy.exc import SQLAlchemyError
from fastapi.responses import JSONResponse
from langgraph.checkpoint.memory import MemorySaver
from langchain_core.messages import AIMessage, HumanMessage
from sqlalchemy.orm import Session

from api.data_model import Chat_Message, AIMessageResponse, ConversationSummary
from api.logs_router import (
    router as logs_router,
)
from config.db_setup import (
    SessionLocal,
    
)
from database.pd_db import (
    get_conversation_history,
    save_summary
)
from error_trace.errorlogger import (
    system_logger,
)

from services.mastercard_solution_tech_stack_agent_module.question_agent.graph_engine import (
    create_graph,
)

from services.mastercard_solution_tech_stack_agent_module.summarizer_agent.summarizer import get_conversation_summary

from services.agent_manger import chat_event, create_chat, get_state

from utilities.helpers import (
    GraphInvocationError,
)

logger = logging.getLogger(__name__)
chat_router = APIRouter()
chat_router.include_router(logs_router)

# === Initialize LangGraph ===
memory = MemorySaver()
graph = create_graph(memory=memory)

GRAPH_CONFIG = {
    "configurable": {
        "conversation_id": "live-chat-session",
        "thread_id": "live-thread-001",
    }
}


# === DB Dependency ===
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# === Extract AIMessage from various structures ===
def _extract_ai_message(response: Union[AIMessage, dict]) -> AIMessage:
    if isinstance(response, AIMessage):
        return response
    elif isinstance(response, dict):
        if isinstance(response.get("message"), AIMessage):
            return response["message"]
        elif isinstance(response.get("messages"), list):
            for msg in reversed(response["messages"]):
                if isinstance(msg, AIMessage):
                    return msg
        elif "content" in response:
            return AIMessage(content=str(response["content"]))
    return AIMessage(content="AI could not generate a valid response.")


# === POST /chat-ai ===
@chat_router.post("/chat-ai", response_model=AIMessageResponse)
async def chat(message: Chat_Message, db: Annotated[Session, Depends(get_db)]):
    """
    Handle AI interaction via LangGraph based on user input.
    """
    try:
        
        response = await chat_event(db=db, message=message)
        ai_message = _extract_ai_message(response)

        return AIMessageResponse(
            content=ai_message.content,
            id=str(response.get("id", "")),
            usage_metadata=getattr(ai_message, "usage_metadata", {}),
            response_metadata=getattr(ai_message, "response_metadata", {}),
            additional_kwargs=getattr(ai_message, "additional_kwargs", {}),
        )

    except GraphInvocationError as e:
        logger.error("AI graph invocation failed: %s", e, exc_info=True)
        system_logger.error(e, exc_info=True)
        return JSONResponse(
            content={"content": "AI service error occurred. Please try again later."},
            status_code=502,
        )
    except Exception as e:
        logger.exception("Unexpected error in /chat-ai route.")
        system_logger.error(e, exc_info=True)
        return JSONResponse(
            content={"content": "Unexpected server error occurred."},
            status_code=500,
        )
    
@chat_router.get("/session-history", response_model_exclude_unset=True)
async def get_chat_history(session_id, db: Annotated[Session, Depends(get_db)]):
    """
    Fetch previous chat history for a given room ID.
    """
    try:
        conversation_history = get_conversation_history(db, session_id=session_id)

        if not conversation_history:
            await create_chat(db=db, session_id=session_id, user_id=str(uuid.uuid4()))
            conversation_history = get_conversation_history(db, session_id=session_id)
        
        return conversation_history
    except SQLAlchemyError as e:
        logger.error("Database error retrieving chat history: %s", e, exc_info=True)
        system_logger.error(e, exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="Failed to retrieve chat history due to database error.",
        ) from e
    
@chat_router.get("/session_state")
async def get_room_state(session_id):
    """
        Fetches the state of a particular room to the front end.
    """
    try:
        session_state = get_state(session_id)

        return jsonable_encoder(session_state)[0]
    
    except Exception as e:
        logger.exception("Unexpected error in /session_state route.")
        system_logger.error(e, exc_info=True)
        return JSONResponse(
            content={"content": "Unexpected server error occurred."},
            status_code=500,
        )
    
@chat_router.get("/conversation_summary", response_model=ConversationSummary)
async def coversation_summary(session_id, db: Annotated[Session, Depends(get_db)]):
    """
        Fetch the conversation summary
    """

    try: 
        session_state = get_state(session_id)

        summary = get_conversation_summary(str(session_state[0]))

        saved_summary = save_summary(db = db, session_id=session_id, summary=summary)

        print(f"Saved summary: {saved_summary}")
        return ConversationSummary(summary=summary)
    except Exception as e:
        logger.exception("Unexpected error in /recommend_stack route.")
        system_logger.error(e, exc_info=True)
        return JSONResponse(
            content={"content": "Unexpected server error occurred."},
            status_code=500,
        )
    
@chat_router.get("/recommeded_stack")
async def recommend_stack(session_id):
    """
        Fetch the recommend stack
    """

    try: 
        session_state = get_state(session_id)

        return get_conversation_summary(str(session_state[0]))
    
    except Exception as e:
        logger.exception("Unexpected error in /recommend_stack route.")
        system_logger.error(e, exc_info=True)
        return JSONResponse(
            content={"content": "Unexpected server error occurred."},
            status_code=500,
        )
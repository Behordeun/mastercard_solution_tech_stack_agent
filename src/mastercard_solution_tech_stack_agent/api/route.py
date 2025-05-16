import uuid
import logging
from typing import Annotated, Union

from fastapi import APIRouter, Depends, HTTPException
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from langchain_core.messages import AIMessage
from langgraph.checkpoint.memory import MemorySaver
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session
from utilities.helpers import GraphInvocationError

from src.mastercard_solution_tech_stack_agent.api.data_model import (
    Chat_Message, ProjectDescriptionRequest, ProjectDescriptionResponse)
from src.mastercard_solution_tech_stack_agent.api.logs_router import \
    router as logs_router
from src.mastercard_solution_tech_stack_agent.config.db_setup import \
    SessionLocal
from src.mastercard_solution_tech_stack_agent.database.pd_db import \
    get_conversation_history
from src.mastercard_solution_tech_stack_agent.database.schemas import \
    AIMessageResponse
from src.mastercard_solution_tech_stack_agent.error_trace.errorlogger import \
    system_logger
from src.mastercard_solution_tech_stack_agent.services.agent_manger import (
    chat_event, create_chat, get_state)
from src.mastercard_solution_tech_stack_agent.services.mastercard_solution_tech_stack_agent_module.question_agent.graph_engine import \
    create_graph

logger = logging.getLogger(__name__)
chat_router = APIRouter()
chat_router.include_router(logs_router)

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
    except (TypeError, IndexError, ValueError) as e:
        logger.exception("Unexpected error in /room_state route.")
        system_logger.error(e, exc_info=True)
        return JSONResponse(
            content={"content": "Unexpected server error occurred."},
            status_code=500,
        )


@chat_router.get("/chat-history", response_model_exclude_unset=True)
async def get_chat_history(room_id, db: Annotated[Session, Depends(get_db)]):
    
@chat_router.get("/session-history", response_model_exclude_unset=True)
async def get_chat_history(session_id, db: Annotated[Session, Depends(get_db)]):
    """
    Fetch previous chat history for a given room ID.
    """
    try:
        conversation_history = get_conversation_history(db, session_id=session_id)

        if not conversation_history:
            await create_chat(db=db, room_id=room_id)
            conversation_history = get_conversation_history(db, room_id=room_id)

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


@chat_router.get("/room_state")
async def get_room_state(room_id):
    """
    Fetches the state of a particular room to the front end.
    """
    try:
        session_state = get_state(session_id)

        return jsonable_encoder(room_state)[0]

    except (IndexError, KeyError) as e:
        logger.exception("No state found for room_id: %s", room_id)
        system_logger.error(e, exc_info=True)
        raise HTTPException(
            status_code=404,
            detail="Room state not found."
        ) from e


@chat_router.post("/project-description", response_model=ProjectDescriptionResponse)
async def project_description(payload: ProjectDescriptionRequest):
    """
    Accepts project title, description, category, and room_id.
    Handles custom category if 'Others' is selected.
    """
    category_display = (
        payload.custom_category
        if payload.category == "Others" and payload.custom_category
        else payload.category
    )

    logger.info(
        "📌 Received project: Title='%s', Category='%s', RoomID='%s'",
        payload.project_title,
        category_display,
        payload.room_id,
    )

    return ProjectDescriptionResponse(
        message=f"Project description received for category: {category_display}",
        data=payload,
    )

    
@chat_router.get("/recommeded_stack")
async def recommend_stack(session_id, db: Annotated[Session, Depends(get_db)]):
    """
        Fetch the recommend stack
    """

    try: 
        session_state = get_state(session_id)
        if session_state.get('done_pillar_step', False) == False:
            return JSONResponse(
                content={"content": "Pillar questions not completed."},
                status_code=400,
            )
        
        summary = get_summary(db, session_id=session_id)
        if summary is None:
            return JSONResponse(
                content={"content": "Summary not found."},
                status_code=404,
            )

        recommend_stack = recommend_teck_stack(session_state['messages'], summary)
        save_techstack(db = db, session_id=session_id, recommended_stack=recommend_stack)

        return JSONResponse(
            content={"content": recommend_stack},
            status_code=200,
        )
    
    except Exception as e:
        logger.exception("Unexpected error in /recommend_stack route.")
        system_logger.error(e, exc_info=True)
        return JSONResponse(
            content={"content": "Unexpected server error occurred."},
            status_code=500,
        )

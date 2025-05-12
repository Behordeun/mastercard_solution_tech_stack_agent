import logging
import re
from typing import Annotated, Union

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse
from langchain_core.messages import AIMessage, HumanMessage
from langgraph.checkpoint.memory import MemorySaver
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from src.mastercard_solution_tech_stack_agent.api.data_model import Chat_Message
from src.mastercard_solution_tech_stack_agent.api.logs_router import (
    router as logs_router,
)
from src.mastercard_solution_tech_stack_agent.config.db_setup import SessionLocal
from src.mastercard_solution_tech_stack_agent.database.pd_db import (
    get_conversation_history,
)
from src.mastercard_solution_tech_stack_agent.database.schemas import AIMessageResponse
from src.mastercard_solution_tech_stack_agent.error_trace.errorlogger import (
    system_logger,
)
from src.mastercard_solution_tech_stack_agent.services.manager import create_chat
from src.mastercard_solution_tech_stack_agent.services.mastercard_solution_tech_stack_agent_module.question_agent.graph_engine import (
    create_graph,
)
from src.mastercard_solution_tech_stack_agent.utilities.helpers import (
    GraphInvocationError,
)

logger = logging.getLogger(__name__)
chat_router = APIRouter()
chat_router.include_router(logs_router)

# Initialize LangGraph AI graph
memory = MemorySaver()
graph = create_graph(memory=memory)

# Config per session
GRAPH_CONFIG = {
    "configurable": {
        "conversation_id": "live-chat-session",
        "thread_id": "live-thread-001",
    }
}


# Dependency to access DB session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# Extract AI message from varied formats
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
    return AIMessage(content="AI could not generate a response.")


@chat_router.post("/chat-ai", response_model=AIMessageResponse)
async def chat(message: Chat_Message, db: Annotated[Session, Depends(get_db)]):
    """
    Route to interact with LangGraph-powered AI using user message.
    """
    try:
        cleaned_message = re.sub(
            r"\[/?INST\]|<\|im_start\|>|<\|im_end\|>", "", message.message
        )
        user_message = HumanMessage(cleaned_message)

        response = await graph.ainvoke(
            {"messages": [user_message]}, config=GRAPH_CONFIG
        )
        ai_message = _extract_ai_message(response)

        return AIMessageResponse(
            content=ai_message.content,
            id=str(response.get("id", "")),
            usage_metadata=getattr(ai_message, "usage_metadata", {}),
            response_metadata=getattr(ai_message, "response_metadata", {}),
            additional_kwargs=getattr(ai_message, "additional_kwargs", {}),
        )
    except GraphInvocationError as e:
        logger.error(f"AI graph invocation failed: {e}", exc_info=True)
        system_logger.error(e, exc_info=True)
        return JSONResponse(
            content={"content": "AI service error occurred. Please try again later."},
            status_code=502,
        )


@chat_router.get("/chat-history", response_model_exclude_unset=True)
async def get_chat_history(room_id: str, db: Annotated[Session, Depends(get_db)]):
    """
    Fetch chat history by room ID.
    """
    try:
        history = get_conversation_history(db, room_id=room_id)
        if not history:
            await create_chat(db=db, room_id=room_id)
    except SQLAlchemyError as e:
        logger.error(f"Database error retrieving chat history: {e}", exc_info=True)
        system_logger.error(e, exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="Failed to retrieve chat history due to database error.",
        ) from e

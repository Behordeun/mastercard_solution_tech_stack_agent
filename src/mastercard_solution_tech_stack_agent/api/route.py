import logging
import re
from typing import Annotated, Union, List

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from langchain_core.messages import AIMessage
from sqlalchemy.orm import Session

from src.mastercard_solution_tech_stack_agent.api.data_model import Chat_Message
from src.mastercard_solution_tech_stack_agent.api.logs_router import router as logs_router
from src.mastercard_solution_tech_stack_agent.config.db_setup import SessionLocal
from src.mastercard_solution_tech_stack_agent.database.schemas import AIMessageResponse
from src.mastercard_solution_tech_stack_agent.database.pd_db import get_conversation_history, insert_conversation
from src.mastercard_solution_tech_stack_agent.error_trace.errorlogger import system_logger  # ✅ Custom logger
from src.mastercard_solution_tech_stack_agent.services.manager import chat_event, create_chat

logger = logging.getLogger(__name__)


# Dependency
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


chat_router = APIRouter()
chat_router.include_router(logs_router)


def _extract_ai_message(response: Union[AIMessage, dict]) -> AIMessage:
    """Extract AI message from a variety of formats."""
    if isinstance(response, AIMessage):
        return response
    elif isinstance(response, dict):
        if isinstance(response.get("message"), AIMessage):
            return response["message"]
        elif isinstance(response.get("messages"), list):
            for msg in reversed(response["messages"]):
                if isinstance(msg, AIMessage):
                    return msg
    return AIMessage(content=str(response.get("message", "Something went wrong.")))


@chat_router.post(
    "/chat-ai",
    response_model=AIMessageResponse,
    response_model_exclude_unset=True,
)
async def chat(message: Chat_Message, db: Annotated[Session, Depends(get_db)]):
    message.message = re.sub(
        r"\[/?INST\]|<\|im_start\|>|<\|im_end\|>", "", message.message
    )

    try:
        response = await chat_event(db, message)
        # logger.info(f"Chat response before serialization: {response}")

        ai_message = _extract_ai_message(response)
        response_id = str(response.get("id") or getattr(ai_message, "id", ""))

        return AIMessageResponse(
            content=ai_message.content,
            id=response_id,
            usage_metadata=getattr(ai_message, "usage_metadata", {}),
            response_metadata=getattr(ai_message, "response_metadata", {}),
            additional_kwargs=getattr(ai_message, "additional_kwargs", {}),
        )

    except Exception as e:
        logger.error(f"Error in chat_ai: {e}", exc_info=True)
        system_logger.error(e, exc_info=True)  # ✅ Log to error.log
        return JSONResponse(
            content={
                "content": "An error occurred. Please try again or contact support."
            },
            status_code=500,
        )

@chat_router.get("/chat-history", response_model_exclude_unset=True)
async def get_chat_history(room_id, db: Annotated[Session, Depends(get_db)]):
    conversation_history = get_conversation_history(db, room_id=room_id)

    if not conversation_history:
        await create_chat(db=db, room_id=room_id)
        conversation_history = get_conversation_history(db, room_id=room_id)
    
    print(conversation_history)
    return conversation_history
import logging
import os
import re
from datetime import datetime
from typing import Annotated, Union

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from langchain_core.messages import AIMessage
from sqlalchemy.orm import Session

from src.mastercard_solution_tech_stack_agent.api.auth import get_current_user
from src.mastercard_solution_tech_stack_agent.api.data_model import Chat_Message, User
from src.mastercard_solution_tech_stack_agent.api.logs_router import (
    router as logs_router,
)
from src.mastercard_solution_tech_stack_agent.api.schemas import AIMessageResponseModel
from src.mastercard_solution_tech_stack_agent.config.db_setup import get_db
from src.mastercard_solution_tech_stack_agent.database.pd_db import (
    get_conversation_history,
)
from src.mastercard_solution_tech_stack_agent.database.schemas import AIMessageResponse
from src.mastercard_solution_tech_stack_agent.services.manager import (
    chat_event,
    create_chat,
)

# === Log directory setup ===
LOG_DIR = "src/mastercard_solution_tech_stack_agent/logs"
os.makedirs(LOG_DIR, exist_ok=True)

# === Log file paths ===
LOG_FILES = {
    "info": os.path.join(LOG_DIR, "info.log"),
    "warning": os.path.join(LOG_DIR, "warning.log"),
    "error": os.path.join(LOG_DIR, "error.log"),
}

# === Logging format ===
log_format = logging.Formatter("%(asctime)s - %(levelname)s - %(name)s - %(message)s")

# === Set up handlers per log level ===
handlers = []
for level, path in LOG_FILES.items():
    handler = logging.FileHandler(path)
    handler.setLevel(getattr(logging, level.upper()))
    handler.setFormatter(log_format)
    handlers.append(handler)

# === Attach handlers to root logger ===
root_logger = logging.getLogger()
root_logger.setLevel(logging.INFO)
root_logger.handlers = []  # Remove existing
for h in handlers:
    root_logger.addHandler(h)
root_logger.addHandler(logging.StreamHandler())  # Console

logger = logging.getLogger(__name__)

router = APIRouter(
    responses={
        200: {"description": "Success - Request was successful."},
        201: {"description": "Created - Resource was successfully created."},
        400: {"description": "Bad Request - Missing or incorrect parameters."},
        401: {"description": "Unauthorized - Login required."},
        403: {"description": "Forbidden - Insufficient permissions."},
        404: {"description": "Not Found - Resource not found."},
        409: {"description": "Conflict - Data conflict occurred."},
        422: {"description": "Unprocessable Entity - Validation error."},
        500: {"description": "Internal Server Error."},
    }
)
router.include_router(logs_router)


def _extract_ai_message(response: Union[AIMessage, dict]) -> AIMessage:
    """Extract AI message from response."""
    if isinstance(response, AIMessage):
        return response
    if isinstance(response, dict):
        if isinstance(response.get("message"), AIMessage):
            return response["message"]
        for msg in reversed(response.get("messages", [])):
            if isinstance(msg, AIMessage):
                return msg
    return AIMessage(content=str(response.get("message", "Something went wrong.")))


@router.post(
    "/chat-ai", response_model=AIMessageResponseModel, response_model_exclude_unset=True
)
async def chat(
    message: Chat_Message,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    """
    Handle chat requests. Only accessible to logged-in users.
    """
    message.message = re.sub(
        r"\[/?INST\]|<\|im_start\|>|<\|im_end\|>", "", message.message
    )

    try:
        logger.info(f"TSA145: Received input: {message.message}")

        # Get conversation history (but not using it in this endpoint)
        _ = get_conversation_history(
            db, room_id=message.roomId, user_id=current_user.id
        )

        # Process the chat
        response = await chat_event(db, message, user_id=current_user.id)
        logger.info(f"TSA145 Response: {response}")
        ai_message = _extract_ai_message(response)

        # Determine response ID
        response_id = (
            response.get("id")
            if isinstance(response, dict)
            else getattr(ai_message, "id", None)
        )
        if response_id is None or not str(response_id).isdigit():
            logger.warning("Invalid or missing response ID. Generating a fallback ID.")
            response_id = int(datetime.now().timestamp())

        # Save response
        new_response = AIMessageResponse(
            user_id=current_user.id,
            profile_id=None,
            content=ai_message.content,
            usage_metadata=getattr(ai_message, "usage_metadata", {}),
            response_metadata=getattr(ai_message, "response_metadata", {}),
            additional_kwargs=getattr(ai_message, "additional_kwargs", {}),
            created_at=datetime.now(),
        )
        try:
            db.add(new_response)
            db.commit()
            db.refresh(new_response)
        except Exception as db_err:
            db.rollback()
            logger.error(f"DB insert failed: {db_err}", exc_info=True)
            return JSONResponse(
                content={"content": "Server error while saving response."},
                status_code=500,
            )

        return AIMessageResponseModel(
            id=new_response.id,
            user_id=new_response.user_id,
            profile_id=new_response.profile_id,
            content=new_response.content,
            usage_metadata=new_response.usage_metadata,
            response_metadata=new_response.response_metadata,
            additional_kwargs=new_response.additional_kwargs,
            created_at=new_response.created_at,
        )

    except Exception as e:
        logger.error(f"Error in /chat-ai: {e}", exc_info=True)
        return JSONResponse(
            content={
                "content": "An error occurred. Please try again or contact support."
            },
            status_code=500,
        )


@router.get("/chat-history", response_model_exclude_unset=True)
async def get_chat_history(
    room_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    """
    Retrieve chat history for a specific room associated with the current user.
    """
    try:
        conversation_history = get_conversation_history(
            db, room_id=room_id, user_id=current_user.id
        )

        if not conversation_history:
            await create_chat(db=db, room_id=room_id, user_id=current_user.id)
            conversation_history = get_conversation_history(
                db, room_id=room_id, user_id=current_user.id
            )

        return conversation_history

    except Exception as e:
        logger.error(f"Error fetching chat history: {e}", exc_info=True)
        return JSONResponse(
            content={"content": "Failed to retrieve chat history."},
            status_code=500,
        )

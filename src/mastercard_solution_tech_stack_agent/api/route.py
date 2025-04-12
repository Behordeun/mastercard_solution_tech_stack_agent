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
from src.mastercard_solution_tech_stack_agent.services.manager import (
    chat_event,
    create_chat,
)

# === Log directory setup ===
LOG_DIR = "src/mastercard_solution_tech_stack_agent/logs"
os.makedirs(LOG_DIR, exist_ok=True)  # Ensure the logs directory exists

# === Log file paths ===
LOG_FILES = {
    "info": os.path.join(LOG_DIR, "info.log"),
    "warning": os.path.join(LOG_DIR, "warning.log"),
    "error": os.path.join(LOG_DIR, "error.log"),
}

# === Logging format ===
log_format = logging.Formatter("%(asctime)s - %(levelname)s - %(name)s - %(message)s")

# === Set up handlers per log level ===
info_handler = logging.FileHandler(LOG_FILES["info"])
info_handler.setLevel(logging.INFO)
info_handler.setFormatter(log_format)

warning_handler = logging.FileHandler(LOG_FILES["warning"])
warning_handler.setLevel(logging.WARNING)
warning_handler.setFormatter(log_format)

error_handler = logging.FileHandler(LOG_FILES["error"])
error_handler.setLevel(logging.ERROR)
error_handler.setFormatter(log_format)

# === Attach handlers to root logger ===
root_logger = logging.getLogger()
root_logger.setLevel(logging.INFO)
root_logger.handlers = []  # Remove default handlers

root_logger.addHandler(info_handler)
root_logger.addHandler(warning_handler)
root_logger.addHandler(error_handler)
root_logger.addHandler(logging.StreamHandler())  # Also log to console

# === Module-level logger ===
logger = logging.getLogger(__name__)


router = APIRouter(
    responses={
        200: {"description": "Success - Request was successful."},
        201: {"description": "Created - Resource was successfully created."},
        400: {
            "description": "Bad Request - The request could not be understood or was missing required parameters."
        },
        401: {
            "description": "Unauthorized - Authentication is required and has failed or not yet been provided."
        },
        403: {
            "description": "Forbidden - The request was valid, but you do not have the necessary permissions."
        },
        404: {"description": "Not Found - The requested resource could not be found."},
        409: {
            "description": "Conflict - The request could not be completed due to a conflict with the current state of the resource."
        },
        422: {
            "description": "Unprocessable Entity - The request was well-formed but could not be followed due to validation errors."
        },
        500: {
            "description": "Internal Server Error - An unexpected server error occurred."
        },
    },
)
router.include_router(logs_router)


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


@router.post(
    "/chat-ai",
    response_model=AIMessageResponseModel,  # Use the updated Pydantic model
    response_model_exclude_unset=True,
)
async def chat(
    message: Chat_Message,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],  # Use User model
):
    """
    Handle chat requests. Only accessible to logged-in users.
    """
    message.message = re.sub(
        r"\[/?INST\]|<\|im_start\|>|<\|im_end\|>", "", message.message
    )

    try:
        # Process the chat event
        response = await chat_event(db, message)

        ai_message = _extract_ai_message(response)
        response_id = str(response.get("id") or getattr(ai_message, "id", ""))

        # Save the AI response to the database
        new_response = AIMessageResponseModel(
            id=response_id,
            user_id=current_user.id,  # Use dot notation
            profile_id=None,  # Update this if profile_id is available
            content=ai_message.content,
            usage_metadata=getattr(ai_message, "usage_metadata", {}),
            response_metadata=getattr(ai_message, "response_metadata", {}),
            additional_kwargs=getattr(ai_message, "additional_kwargs", {}),
            created_at=datetime.now(),  # Replace with actual timestamp if available
        )
        db.add(new_response)
        db.commit()

        return new_response

    except Exception as e:
        logger.error(f"Error in chat_ai: {e}", exc_info=True)
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
    current_user: Annotated[User, Depends(get_current_user)],  # Use User model
):
    """
    Retrieve chat history for a specific room associated with the current user.
    Only accessible to logged-in users.
    """
    # Ensure the room_id belongs to the current user
    conversation_history = get_conversation_history(
        db, room_id=room_id, user_id=current_user.id  # Use dot notation
    )

    if not conversation_history:
        # If no history exists, create a new chat session for the user
        await create_chat(
            db=db, room_id=room_id, user_id=current_user.id
        )  # Use dot notation
        conversation_history = get_conversation_history(
            db, room_id=room_id, user_id=current_user.id  # Use dot notation
        )

    return conversation_history

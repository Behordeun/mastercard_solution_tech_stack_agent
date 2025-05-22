import os
import uuid
from typing import Annotated, List, Union

from fastapi import APIRouter, Depends, HTTPException
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from langchain_core.messages import AIMessage
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from src.mastercard_solution_tech_stack_agent.api.data_model import (
    AIMessageResponse,
    Chat_Message,
    ConversationSummary,
    ProjectDescriptionRequest,
    ProjectDescriptionResponse,
    UserSession,
)
from src.mastercard_solution_tech_stack_agent.api.logs_router import (
    router as logs_router,
)
from src.mastercard_solution_tech_stack_agent.config.db_setup import SessionLocal
from src.mastercard_solution_tech_stack_agent.database.pd_db import (
    get_conversation_history,
    get_summary,
    get_user_sessions,
    save_summary,
    save_techstack,
)
from src.mastercard_solution_tech_stack_agent.database.schemas import User
from src.mastercard_solution_tech_stack_agent.error_trace.errorlogger import (
    system_logger,
)
from src.mastercard_solution_tech_stack_agent.services.agent_manger import (
    chat_event,
    create_chat,
    get_state,
)
from src.mastercard_solution_tech_stack_agent.services.mastercard_solution_tech_stack_agent_module.recommender_agent.recommender import (
    recommend_teck_stack,
)
from src.mastercard_solution_tech_stack_agent.services.mastercard_solution_tech_stack_agent_module.summarizer_agent.summarizer import (
    get_conversation_summary,
)
from src.mastercard_solution_tech_stack_agent.utilities.auth_utils import (
    get_current_user,
)
from src.mastercard_solution_tech_stack_agent.utilities.helpers import (
    GraphInvocationError,
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


router = APIRouter()
router.include_router(logs_router)

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


# === POST /project-description ===
@router.post("/project-description", response_model=ProjectDescriptionResponse)
async def project_description(
    payload: ProjectDescriptionRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    description="Submit a project description including category, title, and session ID. Custom categories are also supported.",
):
    """
    Accepts project title, description, category, and session_id.
    Handles custom category if 'Others' is selected.
    """
    category_display = (
        payload.custom_category
        if payload.category == "Others" and payload.custom_category
        else payload.category
    )

    system_logger.info(
        f"📌 Received project: Title='{payload.project_title}', "
        f"Category='{category_display}', RoomID='{payload.session_id}'"
    )

    return ProjectDescriptionResponse(
        message=f"Project description received for category: {category_display}",
        data=payload,
    )


# === POST /chat-ai ===
@router.post("/chat-ai", response_model=AIMessageResponse)
async def chat(
    message: Chat_Message,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    description="Submit a user message and receive a response from the AI agent powered by LangGraph.",
):
    """
    Handle AI interaction via LangGraph based on user input.
    """
    try:
        system_logger.info("")
        response = await chat_event(
            db=db, message=message, user_id=str(current_user.id)
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
        system_logger.error(e, exc_info=True)
        return JSONResponse(
            content={"content": "AI service error occurred. Please try again later."},
            status_code=502,
        )
    except Exception as e:
        system_logger.error(e, exc_info=True)
        return JSONResponse(
            content={"content": "Unexpected server error occurred."},
            status_code=500,
        )


@router.post("/sessions", response_model=UserSession, status_code=201)
async def create_session(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    description="Create a new user session.",
):
    """
    Create a new session for a user.
    """
    user_id = current_user.id
    session_id = str(uuid.uuid4())  # Generate a new session ID

    try:
        # Create a new session in the database
        new_session = await create_chat(
            db=db, session_id=session_id, user_id=str(user_id)
        )

        # Return the new session details
        return UserSession(session_id=session_id, user_id=str(user_id))
    except SQLAlchemyError as e:
        system_logger.error(
            f"Database error creating new session for user_id {user_id}: {e}",
            exc_info=True,
        )
        raise HTTPException(
            status_code=500,
            detail="Failed to create a new session due to a database error.",
        ) from e


# === GET /user_sessions ===
@router.get("/user_sessions", response_model=List[UserSession])
async def get_all_user_sessions(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    description="Retrieve all sessions created by a specific user.",
):
    """
    Fetch all sessions for a given user ID.
    """
    user_id = current_user.id
    try:
        user_sessions = get_user_sessions(db, user_id=user_id)
        return user_sessions
    except SQLAlchemyError as e:
        system_logger.error(
            f"Database error retrieving user sessions for user_id {user_id}: {e}",
            exc_info=True,
        )
        raise HTTPException(
            status_code=500,
            detail="Failed to retrieve user sessions due to a database error.",
        ) from e


# === GET /session_history ===
@router.get("/chat-history", response_model_exclude_unset=True)
async def get_chat_history(
    session_id,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    description="Retrieve previous conversation history for a given session ID.",
):
    """
    Fetch previous chat history for a given room ID.
    """
    try:
        conversation_history = get_conversation_history(db, session_id=session_id)

        return conversation_history
    except SQLAlchemyError as e:
        system_logger.error(e, exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="Failed to retrieve chat history due to database error.",
        ) from e


# === GET /session_state ===
@router.get("/session_state")
async def get_room_state(
    session_id,
    current_user: Annotated[User, Depends(get_current_user)],
    description="Retrieve the current state (graph memory) of a conversation session.",
):
    """
    Fetches the state of a particular room to the front end.
    """
    try:
        session_state = get_state(session_id)

        return jsonable_encoder(session_state)[0]

    except Exception as e:
        system_logger.error(e, exc_info=True)
        return JSONResponse(
            content={"content": "Unexpected server error occurred."},
            status_code=500,
        )


@router.get("/conversation_summary", response_model=ConversationSummary)
async def coversation_summary(
    session_id,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    description="Get the summarized content of the entire conversation if the pillar stage is completed.",
):
    """
    Fetch the conversation summary
    """

    try:
        session_state = get_state(session_id)

        if session_state.get("done_pillar_step", False) == False:
            return JSONResponse(
                content={"content": "Pillar questions not completed."},
                status_code=400,
            )

        summary = get_conversation_summary(str(session_state["messages"]))
        saved_summary = save_summary(
            db=db, session_id=session_id, summary=summary["conversation"]
        )
        return ConversationSummary(summary=summary["conversation"])
    except Exception as e:
        system_logger.error(e, exc_info=True)
        return JSONResponse(
            content={"content": "Unexpected server error occurred."},
            status_code=500,
        )


@router.get("/recommeded_stack")
async def recommend_stack(
    session_id,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    description="Retrieve a recommended tech stack based on the completed conversation summary.",
):
    """
    Fetch the recommend stack
    """

    try:
        session_state = get_state(session_id)
        if session_state.get("done_pillar_step", False) == False:
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

        recommend_stack = recommend_teck_stack(session_state["messages"], summary)
        save_techstack(db=db, session_id=session_id, recommended_stack=recommend_stack)

        return JSONResponse(
            content={"content": recommend_stack},
            status_code=200,
        )

    except Exception as e:
        system_logger.error(e, exc_info=True)
        return JSONResponse(
            content={"content": "Unexpected server error occurred."},
            status_code=500,
        )

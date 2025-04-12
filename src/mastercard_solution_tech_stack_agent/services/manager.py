import asyncio
import logging
import os
from functools import partial, wraps
from typing import Any, Callable, Dict, List

from langchain_core.messages import AIMessage

from src.mastercard_solution_tech_stack_agent.api.data_model import (
    Chat_Message,
    Chat_Response,
)
from src.mastercard_solution_tech_stack_agent.api.schemas import ChatMessageSchema
from src.mastercard_solution_tech_stack_agent.database.pd_db import (
    DatabaseSession,
    get_conversation_history,
    insert_conversation,
)
from src.mastercard_solution_tech_stack_agent.database.schemas import ChatLog
from src.mastercard_solution_tech_stack_agent.error_trace.errorlogger import (
    system_logger,
)
from src.mastercard_solution_tech_stack_agent.services.mastercard_solution_tech_stack_agent_module.agent import (
    ConversationStage,
    agent,
    prompt_template,
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


class ChatProcessingError(Exception):
    pass


class DatabaseOperationError(ChatProcessingError):
    pass


class WorkflowError(ChatProcessingError):
    pass


def async_retry_decorator(max_attempts: int = 3, base_wait: float = 1) -> Callable:
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            for attempt in range(max_attempts):
                try:
                    return await func(*args, **kwargs)
                except Exception as e:
                    if attempt == max_attempts - 1:
                        system_logger.error(e, exc_info=True)
                        raise
                    await asyncio.sleep(base_wait * (2**attempt))

        return wrapper

    return decorator


async def safe_db_operation(operation: Callable, *args: Any, **kwargs: Any) -> Any:
    try:
        if asyncio.iscoroutinefunction(operation):
            return await operation(*args, **kwargs)
        loop = asyncio.get_event_loop()
        func_with_args = partial(operation, *args, **kwargs)
        return await loop.run_in_executor(None, func_with_args)
    except Exception as e:
        system_logger.error(e, exc_info=True)
        raise DatabaseOperationError(str(e)) from e


def extract_persona_and_tags(message: str) -> tuple[str, List[str]]:
    tags = []
    persona = None

    message_lower = message.lower()

    if "solution architect" in message_lower or "🧠" in message:
        persona = "AI Solution Architect"
        tags.append("architecture")

    if "project goal" in message_lower:
        tags.append("project kickoff")

    if "marketing" in message_lower:
        persona = "Marketing Strategist"
        tags.extend(["strategy", "market research"])

    if "fundraising" in message_lower or "startup" in message_lower:
        persona = "Startup Advisor"
        tags.append("venture")

    if "let's" in message_lower:
        tags.append("conversational")

    return persona, tags


class ChatProcessor:
    def __init__(self, db: Any):
        self.db = db

    async def log_and_respond(
        self,
        message_dict: Dict[str, Any],
        ai_message: str,
        user_id: int,
        usage_metadata: Dict[str, Any] = None,
        system_message: str = "",
        loggable: bool = True,
    ) -> Dict[str, Any]:
        try:
            if loggable and system_message:
                message_dict["message"] = system_message

            if user_id is None:
                raise ValueError(
                    "user_id is required but was not provided to log_and_respond"
                )

            persona, tags = extract_persona_and_tags(ai_message)

            with DatabaseSession() as session:
                room_id = message_dict.get("roomId") or message_dict.get("room_id")
                if not room_id:
                    raise ValueError("room_id is required and missing in message_dict")

                session.add(
                    ChatLog(
                        room_id=room_id,
                        user_id=user_id,
                        user_message=message_dict.get("message"),
                        ai_response=ai_message,
                        system_note=system_message.replace("SYSTEM: ", ""),
                        resource_urls=message_dict.get("resourceUrls"),
                    )
                )
                session.commit()

            return Chat_Response(
                id=str(message_dict.get("id")),
                roomId=room_id,
                resourceUrls=message_dict.get("resourceUrls") or [],
                sender="AI",
                message=ai_message,
                tags=tags,
                persona=persona,
                usageMetadata=usage_metadata or {},
            ).model_dump()

        except Exception as e:
            system_logger.error(e, additional_info={"message_dict": message_dict})
            return {
                "id": message_dict.get("id"),
                "roomId": message_dict.get("roomId"),
                "sender": "AI",
                "message": "An error occurred. Please try again or contact support.",
                "resourceUrls": [],
                "tags": [],
            }

    @async_retry_decorator()
    async def handle_graph_integration(
        self, message_dict: Dict[str, Any], user_id: int
    ) -> Dict[str, Any]:
        try:
            messages = await safe_db_operation(
                get_conversation_history,
                self.db,
                room_id=message_dict.get("roomId"),
                user_id=user_id,
            )

            last_message = {
                "messages": [{"role": "user", "content": message_dict.get("message")}]
            }

            config = {
                "configurable": {
                    "conversation_id": message_dict.get("roomId"),
                    "thread_id": message_dict.get("roomId"),
                }
            }

            output = {}
            async for event in agent.astream(last_message, config):
                for value in event.values():
                    output = value

            if not isinstance(output, dict):
                raise ValueError("Graph did not return a valid dictionary.")

            ai_messages = [
                msg.content
                for msg in output.get("messages", [])
                if isinstance(msg, AIMessage)
            ]
            if not ai_messages:
                raise ValueError("No AI response generated.")

            ai_message = ai_messages[-1].strip()
            usage_metadata = output.get("usage_metadata", {})

            return await self.log_and_respond(
                message_dict,
                ai_message,
                user_id=user_id,
                usage_metadata=usage_metadata,
            )

        except asyncio.TimeoutError as e:
            system_logger.error(e, exc_info=True)
            return await self.log_and_respond(
                message_dict,
                "Request timed out. Please try again.",
                user_id=user_id,
                loggable=False,
            )
        except Exception as e:
            system_logger.error(e, exc_info=True)
            return await self.log_and_respond(
                message_dict,
                "We're experiencing technical difficulties. Please try again.",
                user_id=user_id,
                loggable=False,
            )


async def chat_event(db: Any, message: Chat_Message, user_id: int) -> Dict[str, Any]:
    logger.info(f"TSA145: Received input: {message.message}")

    try:
        if not message.message.strip():
            return {"message": "No input provided."}

        validated = ChatMessageSchema(**message.model_dump())
        chat_processor = ChatProcessor(db)
        response = await chat_processor.handle_graph_integration(
            validated.dict(), user_id
        )

        logger.info(f"TSA145 Response: {response['message']}")

        insert_conversation(
            db,
            ai_message=response["message"],
            room_id=message.roomId,
            user_id=user_id,
            user_message=message.message,
        )
        return response

    except Exception as e:
        system_logger.error(e, exc_info=True)
        return {
            "message": "AI processing error. Please try again later.",
            "sender": "AI",
        }


async def create_chat(db: Any, room_id: str, user_id: int) -> Dict[str, Any]:
    logger.info(f"Create Chat for user_id={user_id}, room_id={room_id}")

    try:
        insert_conversation(
            db,
            ai_message=prompt_template.get("OPENING_TEXT", ""),
            room_id=room_id,
            user_id=user_id,
            user_message="",
        )

        config = {
            "configurable": {
                "conversation_id": room_id,
                "thread_id": room_id,
            }
        }
        agent.update_state(
            config,
            {
                "messages": AIMessage(content=prompt_template.get("OPENING_TEXT", "")),
                "conversation_stage": ConversationStage.greeting,
            },
        )

        return {
            "message": "Chat session created successfully.",
            "sender": "AI",
        }

    except Exception as e:
        system_logger.error(e, exc_info=True)
        return {
            "message": "AI processing error. Please try again later.",
            "sender": "AI",
        }

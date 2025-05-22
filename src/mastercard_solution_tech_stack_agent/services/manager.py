import asyncio
import uuid
from functools import wraps
from typing import Any, Callable, Dict

from langchain_core.messages import AIMessage

from src.mastercard_solution_tech_stack_agent.api.data_model import (
    Chat_Message,
    Chat_Response,
)
from src.mastercard_solution_tech_stack_agent.config.settings import env_config
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

db_uri = f"postgresql://{env_config.user}:{env_config.password}@{env_config.host}/{env_config.database}"


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
        return await loop.run_in_executor(None, operation, *args, **kwargs)
    except Exception as e:
        system_logger.error(e, exc_info=True)
        raise DatabaseOperationError(str(e)) from e


class ChatProcessor:
    def __init__(self, db: Any):
        self.db = db

    async def log_and_respond(
        self,
        message_dict: Dict[str, Any],
        ai_message: str,
        system_message: str = "",
        loggable: bool = True,
    ) -> Dict[str, Any]:
        try:
            if loggable and system_message:
                message_dict["message"] = system_message

            user_id = message_dict.get("user_id") or str(uuid.uuid4())
            session_id = message_dict.get("roomId") or message_dict.get("session_id")
            if not session_id:
                raise ValueError("Missing 'session_id' in message")

            with DatabaseSession() as session:
                session.add(
                    ChatLog(
                        session_id=session_id,
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
                roomId=session_id,
                resourceUrls=message_dict.get("resourceUrls"),
                sender="AI",
                message=ai_message,
                tags=message_dict.get("tags"),
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
        self, message_dict: Dict[str, Any]
    ) -> Dict[str, Any]:
        try:
            messages = await safe_db_operation(
                get_conversation_history, self.db, message_dict.get("roomId")
            )
            system_logger.info(f"Conversation history: {messages}")

            last_message = {
                "messages": [{"role": "user", "content": message_dict.get("message")}]
            }

            config = {
                "configurable": {
                    "conversation_id": message_dict.get("roomId"),
                    "thread_id": message_dict.get("roomId"),
                }
            }

            async for event in agent.astream(last_message, config):
                for value in event.values():
                    output = value
                    print(f"Assistant: {value['messages'][-1]}")

            if not isinstance(output, dict):
                raise ValueError("Graph output is not a dictionary.")

            ai_messages = [
                msg.content
                for msg in output.get("messages", [])
                if isinstance(msg, AIMessage)
            ]
            if not ai_messages:
                raise ValueError("No AI message returned.")

            return await self.log_and_respond(message_dict, ai_messages[-1].strip())

        except asyncio.TimeoutError as e:
            system_logger.error(e, exc_info=True)
            return await self.log_and_respond(
                message_dict, "Request timed out. Please try again.", "", False
            )
        except Exception as e:
            system_logger.error(e, exc_info=True)
            return await self.log_and_respond(
                message_dict,
                "We're experiencing technical difficulties. Please try again.",
                "",
                False,
            )


async def chat_event(db: Any, message: Chat_Message) -> Dict[str, Any]:
    system_logger.info(f"TSA145: Received input: {message.message}")

    try:
        if not message.message.strip():
            return {"message": "No input provided."}

        chat_processor = ChatProcessor(db)
        response = await chat_processor.handle_graph_integration(message.model_dump())

        insert_conversation(
            db,
            ai_message=response["message"],
            session_id=message.roomId,
            user_message=message.message,
            user_id=str(uuid.uuid4()),
        )

        return response

    except Exception as e:
        system_logger.error(e, exc_info=True)
        return {
            "message": "AI processing error. Please try again later.",
            "sender": "AI",
        }


async def create_chat(db: Any, session_id: str) -> Dict[str, Any]:
    system_logger.info("TSA145: Create Chat started")

    try:
        user_id = str(uuid.uuid4())
        insert_conversation(
            db,
            ai_message=prompt_template.get("OPENING_TEXT", ""),
            session_id=session_id,
            user_message="",
            user_id=user_id,
        )

        config = {
            "configurable": {
                "conversation_id": session_id,
                "thread_id": session_id,
            }
        }
        agent.update_state(
            config,
            {
                "messages": AIMessage(content=prompt_template.get("OPENING_TEXT", "")),
                "conversation_stage": ConversationStage.greeting,
            },
        )

    except Exception as e:
        system_logger.error(e, exc_info=True)
        return {
            "message": "AI processing error. Please try again later.",
            "sender": "AI",
        }

import asyncio
import logging
from functools import wraps
from typing import Any, Callable, Dict, List

from langchain_core.messages import AIMessage
from langgraph.checkpoint.memory import MemorySaver

from src.api.data_model import Chat_Message, Chat_Response
from src.database.pd_db import DatabaseSession, get_conversation_history, insert_conversation
from src.database.schemas import ChatLog
from src.error_trace.errorlogger import system_logger
from src.services.mastercard_solution_tech_stack_agent_module.agent import agent, prompt_template, ConversationStage

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
        else:
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

            with DatabaseSession() as session:
                room_id = message_dict.get("roomId") or message_dict.get("room_id")
                if not room_id:
                    raise ValueError("room_id is required and missing in message_dict")

                session.add(
                    ChatLog(
                        room_id=room_id,
                        user_message=message_dict.get("message"),
                        ai_response=ai_message,
                        system_note=system_message.replace("SYSTEM: ", ""),
                        resource_urls=message_dict.get("resourceUrls"),
                    )
                )
                session.commit()

            return Chat_Response(
                id=str(message_dict.get("id")),
                roomId=message_dict.get("roomId"),
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
            print(f"Conversation history: {messages}")
            
            # messages.append({"role": "user", "content": message_dict.get("message")})
            # state = {
            #     "messages": messages,
            #     "user_interaction_count": len(
            #         [m for m in messages if m["role"] == "user"]
            #     ),
            #     "last_message": None,
            #     "last_user_response": None,
            #     "program_context": {},
            #     "pillar_responses": {},
            #     "asked_questions": [],
            #     "current_pillar": None,
            #     "completed_pillars": [],
            #     "summary_confirmed": False,
            #     "recommended_stack": None,
            #     "tech_stack_ready": False,
            # }

            # graph = techstack_agent_graph()
            
            last_message = {"messages": [{"role": "user", "content": message_dict.get("message")}]}

            print("Last Message:", last_message)
            config = {
                "configurable": {
                    "conversation_id": message_dict.get("roomId"),
                    "thread_id": message_dict.get("roomId"),
                }
            }

            # ✅ Fix: Use async invocation
            async for event in agent.astream(last_message, config):
                for value in event.values():
                    output = value
                    print(f"Assistant {value['messages'][-1]}")

            if not isinstance(output, dict):
                raise ValueError("Graph did not return a valid dictionary.")

            ai_messages: List[str] = [
                msg.content
                for msg in output.get("messages", [])
                if isinstance(msg, AIMessage)
            ]
            if not ai_messages:
                raise ValueError("No AI response generated.")

            ai_message = ai_messages[-1].strip()
            return await self.log_and_respond(message_dict, ai_message)

        except asyncio.TimeoutError as e:
            system_logger.error(e, exc_info=True)
            return await self.log_and_respond(
                message_dict, "Request timed out. Please try again.", "", False
            )

        except Exception as e:
            print(e)
            system_logger.error(e, exc_info=True)
            return await self.log_and_respond(
                message_dict,
                "We're experiencing technical difficulties. Please try again.",
                "",
                False,
            )


async def chat_event(db: Any, message: Chat_Message) -> Dict[str, Any]:
    logger.info(f"TSA145: Received input: {message.message}")

    try:
        if not message.message.strip():
            return {"message": "No input provided."}

        chat_processor = ChatProcessor(db)
        response = await chat_processor.handle_graph_integration(message.model_dump())
        
        print(f"TSA145 Response: {response['message']}")

        insert_conversation(db, ai_message=response["message"],
                            room_id=message.roomId, user_message=message.message)
        # logger.info(f"TSA145 Response: {response['message']}")
        return response

    except Exception as e:
        system_logger.error(e, exc_info=True)
        return {
            "message": "AI processing error. Please try again later.",
            "sender": "AI",
        }


async def create_chat(db: Any, room_id) -> Dict[str, Any]:
    logger.info(f"Create Chat")

    try:        
        # print(prompt_template.get("OPENING_TEXT", ""))
        insert_conversation(db, ai_message=prompt_template.get("OPENING_TEXT", ""),
                            room_id=room_id, user_message="")
        
        config = {
            "configurable": {
                "conversation_id": room_id,
                "thread_id": room_id,
            }
        }
        agent.update_state(config, {"messages": AIMessage(content = prompt_template.get("OPENING_TEXT", "")),
                                    "conversation_stage": ConversationStage.greeting})

    except Exception as e:
        system_logger.error(e, exc_info=True)
        return {
            "message": "AI processing error. Please try again later.",
            "sender": "AI",
        }

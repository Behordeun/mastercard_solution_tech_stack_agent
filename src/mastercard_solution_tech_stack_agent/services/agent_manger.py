from typing import Any, Callable, Dict
from api.data_model import (
    Chat_Message,
    Chat_Response,
)
from psycopg_pool import AsyncConnectionPool

from langchain_core.messages import AIMessage, HumanMessage

from database.pd_db import (
    DatabaseSession,
    get_conversation_history,
    insert_conversation,
)
import uuid
import logging
from error_trace.errorlogger import (
    system_logger,
)

from services.mastercard_solution_tech_stack_agent_module.agent import (
    ConversationStage,
    agent,
    prompt_template,
)

from langgraph.checkpoint.postgres import PostgresSaver
from langgraph.checkpoint.memory import MemorySaver
from services.mastercard_solution_tech_stack_agent_module.question_agent.graph_engine import (
    create_graph
)

logger = logging.getLogger(__name__)

connection_kwargs = {
    "autocommit": True,
    "prepare_threshold": 0,
}
from config.settings import env_config

# db_uri = f"postgresql://{env_config.user}:{env_config.password}@{env_config.host}/{env_config.database}"

# with PostgresSaver.from_conn_string(db_uri) as checkpointer:
#     graph = create_graph(checkpointer=checkpointer)

# pool = AsyncConnectionPool(conninfo=db_uri, max_size=20, kwargs=connection_kwargs)
# checkpointer = AsyncPostgresSaver(pool)

# === Initialize LangGraph ===
memory = MemorySaver()
graph = create_graph(memory=memory)

async def chat_event(db: Any, message: Chat_Message) -> Dict[str, Any]:
    logger.info(f"TSA145: Received input: {message.message}")

    try:
        if not message.message.strip():
            return {"message": "No input provided."}
        
        config = {
            "configurable": {
                "conversation_id": message.roomId,
                "thread_id": message.roomId,
            }
        }

        user_message = HumanMessage(message.message)

        response = await graph.ainvoke(
            {"messages": [user_message]},
            config
        )

        insert_conversation(
            db,
            ai_message=response['messages'][-1].content,
            room_id=message.roomId,
            user_message=message.message,
            user_id=str(uuid.uuid4()),
        )

        return response

    except Exception as e:
        print(e)
        system_logger.error(e, exc_info=True)

        return {
            "message": "AI processing error. Please try again later.",
            "sender": "AI",
        }

async def create_chat(db: Any, room_id: str) -> Dict[str, Any]:
    logger.info(f"Create Chat")

    try:
        user_id = str(uuid.uuid4())
        insert_conversation(
            db,
            ai_message=prompt_template.get("OPENING_TEXT", ""),
            room_id=room_id,
            user_message="",
            user_id=user_id,
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

    except Exception as e:
        system_logger.error(e, exc_info=True)
        return {
            "message": "AI processing error. Please try again later.",
            "sender": "AI",
        }

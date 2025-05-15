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
    create_session
)
import uuid
import logging
import uuid
from typing import Any, Dict

from api.data_model import Chat_Message
from database.pd_db import insert_conversation
from error_trace.errorlogger import system_logger
from langchain_core.messages import HumanMessage
from langgraph.checkpoint.postgres import PostgresSaver
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from psycopg_pool import AsyncConnectionPool
from services.mastercard_solution_tech_stack_agent_module.question_agent.graph_engine import (
    create_graph,
)

logger = logging.getLogger(__name__)

connection_kwargs = {
    "autocommit": True,
    "prepare_threshold": 0,
}
from config.settings import env_config

# === Initialize LangGraph ===
# DB_URI = "postgresql://postgres:postgres@localhost:5442/postgres?sslmode=disable"
db_uri = f"postgresql://{env_config.user}:{env_config.password}@{env_config.host}/{env_config.database}?sslmode=disable"

# memory = MemorySaver()
# graph = create_graph(memory=memory)


def invoke(user_message, config):
    with PostgresSaver.from_conn_string(db_uri) as checkpointer:
        checkpointer.setup()

        graph = create_graph(checkpointer=checkpointer)

        response = graph.invoke({"messages": [user_message]}, config)

    return response

<<<<<<< HEAD
async def ainvoke(user_message, config):
    with AsyncConnectionPool(conninfo=db_uri, max_size=20, kwargs=connection_kwargs,) as pool:
        checkpointer = AsyncPostgresSaver(pool)
        graph = create_graph(checkpointer=checkpointer)

        response = graph.invoke(
            {"messages": [user_message]},
            config
        )

    return response

def get_state(session_id):
    config = {
        "configurable": {
            "conversation_id": session_id,
            "thread_id": session_id,
        }
    }

    with PostgresSaver.from_conn_string(db_uri) as checkpointer:
        checkpointer.setup()

        graph = create_graph(checkpointer=checkpointer)

        graph_state = graph.get_state(config)

    return graph_state.values

async def chat_event(db: Any, message: Chat_Message, user_id = str(uuid.uuid4())) -> Dict[str, Any]:
    logger.info(f"TSA145: Received input: {message.message}")

    try:
        if not message.message.strip():
            return {"message": "No input provided."}

        config = {
            "configurable": {
                "conversation_id": message.session_id,
                "thread_id": message.session_id,
            }
        }

        user_message = HumanMessage(message.message)

        response = invoke(user_message, config)

        insert_conversation(
            db,
            ai_message=response['messages'][-1].content,
            session_id=message.session_id,
            user_message=message.message,
            user_id=user_id,
        )

        return response

    except Exception as e:
        print(f"Except: {e}")
        system_logger.error(e, exc_info=True)

        return {
            "message": "AI processing error. Please try again later.",
            "sender": "AI",
        }

async def create_chat(db: Any, session_id: str, user_id) -> Dict[str, Any]:
    logger.info(f"Create Chat")

    try:
        config = {
            "configurable": {
                "conversation_id": session_id,
                "thread_id": session_id,
            }
        }

        user_message = HumanMessage("")

        response = invoke(user_message, config)

        create_session(
            db,
            session_id=session_id,
            user_id=user_id,
        )


        insert_conversation(
            db,
            ai_message=response['messages'][-1].content,
            session_id=session_id,
            user_message="",
            user_id=user_id,
        )

    except Exception as e:
        system_logger.error(e, exc_info=True)
        return {
            "message": "AI processing error. Please try again later.",
            "sender": "AI",
        }

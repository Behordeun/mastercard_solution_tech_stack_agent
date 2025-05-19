from typing import Any, Dict

from langchain_core.messages import HumanMessage
from langgraph.checkpoint.postgres import PostgresSaver
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from psycopg_pool import AsyncConnectionPool

from src.mastercard_solution_tech_stack_agent.api.data_model import Chat_Message
from src.mastercard_solution_tech_stack_agent.config.settings import env_config
from src.mastercard_solution_tech_stack_agent.database.pd_db import (
    create_session,
    insert_conversation,
)
from src.mastercard_solution_tech_stack_agent.error_trace.errorlogger import (
    system_logger,
)
from src.mastercard_solution_tech_stack_agent.services.mastercard_solution_tech_stack_agent_module.question_agent.graph_engine import (
    create_graph,
)

# PostgreSQL connection string setup
db_uri = f"postgresql://{env_config.user}:{env_config.password}@{env_config.host}/{env_config.database}?sslmode=disable"

connection_kwargs = {
    "autocommit": True,
    "prepare_threshold": 0,
}


# === SYNC LangGraph invocation ===
def invoke(user_message, config):
    with PostgresSaver.from_conn_string(db_uri) as checkpointer:
        checkpointer.setup()
        graph = create_graph(checkpointer=checkpointer)
        response = graph.invoke({"messages": [user_message]}, config)
    return response


# === ASYNC LangGraph invocation ===
async def ainvoke(user_message, config):
    async with AsyncConnectionPool(
        conninfo=db_uri,
        max_size=20,
        kwargs=connection_kwargs,
    ) as pool:
        checkpointer = AsyncPostgresSaver(pool)
        graph = create_graph(checkpointer=checkpointer)
        response = graph.invoke({"messages": [user_message]}, config)
    return response


# === LangGraph state retrieval ===
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
    return graph_state


# === Chat Event Handler ===
async def chat_event(db: Any, message: Chat_Message, user_id: str) -> Dict[str, Any]:
    system_logger.info(f"TSA145: Received input: {message.message}")

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

        ai_response = (
            response["messages"][-1].content
            if response.get("messages")
            else "No AI response"
        )

        insert_conversation(
            db=db,
            session_id=message.session_id,
            user_message=message.message,
            ai_message=ai_response,
            user_id=user_id,
        )

        return response

    except Exception as e:
        system_logger.error(
            e, additional_info={"context": "chat_event failed"}, exc_info=True
        )
        return {
            "message": "AI processing error. Please try again later.",
            "sender": "AI",
        }


# === Create Initial Chat Session ===
async def create_chat(db: Any, session_id: str, user_id: str) -> Dict[str, Any]:
    system_logger.info("TSA145: Create Chat started")

    try:
        config = {
            "configurable": {
                "conversation_id": session_id,
                "thread_id": session_id,
            }
        }

        user_message = HumanMessage("")
        response = invoke(user_message, config)

        ai_response = (
            response["messages"][-1].content if response.get("messages") else "Welcome."
        )

        create_session(
            db=db,
            session_id=session_id,
            user_id=user_id,
        )

        insert_conversation(
            db=db,
            session_id=session_id,
            user_message="",
            ai_message=ai_response,
            user_id=user_id,
        )

        return response

    except Exception as e:
        system_logger.error(
            e, additional_info={"Context": "create_chat failed"}, exc_info=True
        )
        return {
            "message": "AI processing error. Please try again later.",
            "sender": "AI",
        }

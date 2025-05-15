from langchain_core.messages import HumanMessage
from langgraph.checkpoint.memory import MemorySaver
from psycopg_pool import AsyncConnectionPool
from services.manager import db_uri
from services.mastercard_solution_tech_stack_agent_module.utils import display_graph

from .graph_engine import create_graph


async def main():
    import random

    test_sample = random.randint(1, 1000)
    prompts = [
        "",
        "The goal of this project is to build a family planning chatbot",
        "The chatbot informs the user of various planning method and how to use contraceptives",
        "Eductaion",
        "The chatbot is going to be deployed on whatapp, telegram and on a website",
    ]
    # test_sample = 758

    display_graph(create_graph())

    connection_kwargs = {
        "autocommit": True,
        "prepare_threshold": 0,
    }

    async with AsyncConnectionPool(
        # Example configuration
        conninfo=db_uri,
        max_size=20,
        kwargs=connection_kwargs,
    ) as pool:
        memory = MemorySaver()

        graph = create_graph(memory=memory)

        config = {
            "configurable": {
                "conversation_id": f"Test {test_sample}",
                "thread_id": f"Test {test_sample}",
            }
        }

        print(config)

        while True:
            # for user_input in prompts:
            # Get user input
            print("=" * 100)
            print("You: ", end="")
            user_input = input("You: ")
            # print(user_input)
            if user_input.lower() == "exit":
                break
            print("-" * 100)

            # Create a message object for the user input
            user_message = HumanMessage(user_input)

            # Add the user message to the graph and get the response
            res = await graph.ainvoke({"messages": [user_message]}, config)
            # checkpoint = await checkpointer.aget(config)

            print("-" * 100)
            print("AI: ", end="")
            print(res["messages"][-1].content.strip())
            print("=" * 100)


if __name__ == "__main__":
    # Run the main function in an asyncio event loop
    import asyncio
    import sys

    # Fix for Windows
    if sys.platform.startswith("win"):
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    asyncio.run(main())

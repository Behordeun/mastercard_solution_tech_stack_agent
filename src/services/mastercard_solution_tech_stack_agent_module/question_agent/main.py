from psycopg_pool import AsyncConnectionPool
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

from src.services.model import agent_model as llm
from src.services.manager import db_uri
from src.services.mastercard_solution_tech_stack_agent_module.utils import display_graph

from .utils import (
    AgentState,
    ConversationStage, 
    domain_knowledge_manager)


from .prompts import (
    prompt_description_prompt,
    domain_prompt,
    specify_goal_prompt,
)

from .nodes import (
    greeting_node,
    pillar_questions_marker_node,
    pillar_questions_gen_node,
    pillar_questions_node,
    summary_node, 
    craft_question_node,
)


from langchain_core.messages import HumanMessage

from langgraph.graph import StateGraph, END, START
from langgraph.checkpoint.memory import MemorySaver


def stage_update(state: AgentState):
    '''
    Updates the state of the conversation based on the current stage.
    '''
    # Logic to update the state based on the current stage    
    state["user_interaction_count"] = state.get("user_interaction_count", 0) + 1
    state["last_message"] = state["messages"][-1].content if state["messages"] else None
    
    if state["messages"][-1].type == "human":
        state["last_user_response"] = state["messages"][-1].content

    conv_stage = state.get("conversation_stage", None)
    answered_questions = state.get("answered_questions", {})
        
    if not conv_stage:
        conv_stage = ConversationStage.greeting
    elif conv_stage and state.get('last_user_response') is not None:
        if conv_stage == ConversationStage.greeting:
            answered_questions["Goal"] = state["last_user_response"]
            conv_stage = ConversationStage.project_description
        elif conv_stage == ConversationStage.project_description:
            answered_questions["Project Description"] = state["last_user_response"]
            conv_stage = ConversationStage.domain
        elif conv_stage == ConversationStage.domain:
            answered_questions["Domain"] = state["last_user_response"]
            conv_stage = ConversationStage.specify_goal
        elif conv_stage == ConversationStage.specify_goal:
            answered_questions["Specify Goal"] = state["last_user_response"]    
            conv_stage = ConversationStage.pillar_questions
        elif conv_stage == ConversationStage.pillar_questions:
            if state['done_pillar_step'] == False:
                conv_stage = ConversationStage.pillar_questions
            else:
                answered_questions["Domain"] = state["last_user_response"]
                conv_stage = ConversationStage.summary
        elif conv_stage == ConversationStage.summary:
            if state['summary_confirmed'] == False:
                answered_questions["Domain"] = state["last_user_response"]
                conv_stage = ConversationStage.summary
            else:
                answered_questions["Domain"] = state["last_user_response"]
                conv_stage = ConversationStage.end_of_conversation
        
    state["answered_questions"] = answered_questions
    state["conversation_stage"] = conv_stage
    print(state['conversation_stage'])
    return state

def route_step(state: AgentState):
    """
    Routes a step based on the current state.
    """
    # Logic to determine the next step based on the state
    conv_stage = state.get("conversation_stage", None)
    
    if conv_stage: 
        if conv_stage == ConversationStage.end_of_conversation:
            return END
        return conv_stage.value
    else:
        return END

def create_graph(checkpointer: AsyncPostgresSaver = None, memory: MemorySaver = None) -> StateGraph:
    """
    Creates the LangGraph graph.
    """
    graph = StateGraph(AgentState)  

    # Add nodes for different conversation stages
    graph.add_node("stage_update", stage_update)
    graph.add_node(ConversationStage.greeting.value, greeting_node)
    graph.add_node(ConversationStage.project_description.value,
                   lambda state, config: craft_question_node(state = state, prompt = prompt_description_prompt))
    graph.add_node(ConversationStage.domain.value, 
                   lambda state, config: craft_question_node(state = state, prompt = domain_prompt, parameters={"domains": domain_knowledge_manager.knowledge}))
    graph.add_node(ConversationStage.pillar_questions.value, pillar_questions_node)
    graph.add_node("pillar_question_marker", pillar_questions_marker_node)
    graph.add_node("pillar_question_generator", pillar_questions_gen_node)
    graph.add_node(ConversationStage.summary.value, summary_node)
    
    
    # Build the graph structure
    graph.add_edge(START, "stage_update",)
    graph.add_edge(ConversationStage.greeting.value, END)
    graph.add_edge(ConversationStage.project_description.value, END)
    graph.add_edge(ConversationStage.domain.value, END)
    graph.add_edge(ConversationStage.pillar_questions.value, "pillar_question_marker")
    graph.add_edge("pillar_question_marker", "pillar_question_generator")
    graph.add_edge("pillar_question_generator", END)

    # Add Conditional edges based on the conversation stage
    graph.add_conditional_edges(
        "stage_update",
        route_step,
        {
            ConversationStage.greeting.value: ConversationStage.greeting.value,
            ConversationStage.project_description.value: ConversationStage.project_description.value,
            ConversationStage.domain.value: ConversationStage.domain.value,
            ConversationStage.pillar_questions.value: ConversationStage.pillar_questions.value,
            ConversationStage.summary.value: ConversationStage.summary.value,
        },
    )

    if memory:
        # Add a memory saver to the graph
        return graph.compile(memory)
    
    if checkpointer:
    # Compile
        return graph.compile(checkpointer=checkpointer)
    
    return graph.compile()


async def main():
    import random
    test_sample = random.randint(1, 1000)
    prompts = ['',
               "The goal of this project is to build a family planning chatbot",
               "The chatbot informs the user of various planning method and how to use contraceptives"]
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
        # checkpointer = AsyncPostgresSaver(pool)
        memory = MemorySaver()

        graph = create_graph(memory=memory)

        config = {
            "configurable": {
                "conversation_id": f"Test {test_sample}",
                "thread_id": f"Test {test_sample}",
            }
        }

        print(config)

        for user_input in prompts:
            # Get user input
            print("=" * 100)
            print("You: ", end="")
            print(user_input)
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

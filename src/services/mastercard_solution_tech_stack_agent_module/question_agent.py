from typing import Annotated, Dict, List, Optional, Tuple
from typing_extensions import TypedDict
from psycopg_pool import AsyncConnectionPool
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

from src.services.model import agent_model as llm
from src.services.manager import db_uri
from src.services.mastercard_solution_tech_stack_agent_module.utils import display_graph

from langchain.prompts import load_prompt
from langchain_core.runnables import RunnableConfig
from langgraph.graph.message import AnyMessage, add_messages
from langchain_core.messages import AIMessage, HumanMessage

from langgraph.graph import StateGraph, END, START
from langgraph.checkpoint.memory import MemorySaver

from enum import Enum

# Fetch all prompts
greeting_prompt = load_prompt("src/services/mastercard_solution_tech_stack_agent_module/prompts/greeting.yaml")
prompt_description = load_prompt("src/services/mastercard_solution_tech_stack_agent_module/prompts/project_description.yaml")
# print(greeting_prompt)

class ConversationStage(Enum):
    greeting = "greeting"
    project_description = "project_description"
    domain = "domain"
    pillar_questions = "pillar_questions"
    specify_goal = "specify goal"
    summary = "summary"
    end_of_conversation = "end_of_conversation"

# === STATE ===
class AgentState(TypedDict):
    messages: Annotated[List[AnyMessage], add_messages]     # List of messages in the conversation 
    conversation_stage: ConversationStage                   # Current stage of the conversation
    user_interaction_count: int                             # Number of interactions with the user
    last_message: Optional[str]                             # Last message sent to the user
    last_user_response: Optional[str]                       # Last response from the user
    pillar_responses: Dict[str, Dict[str, str]]             # Responses to pillar questions
    answered_questions: Dict[str, str]                      # List of answered by the user, with question and answer pairs
    current_pillar: Optional[str]                           # Current pillar being discussed
    completed_pillars: List[str]                            # List of completed pillars
    done_pillar_step: bool = False                          # Whether the current pillar step is done
    summary_confirmed: bool                                 # Whether the summary has been confirmed by the user 

def stage_update(state: AgentState):
    '''
    Updates the state of the conversation based on the current stage.
    '''
    # Logic to update the state based on the current stage
    state["user_interaction_count"] += 1
    state["last_message"] = state["messages"][-1].content if state["messages"] else None
    
    if state["messages"][-1].role == "human":
        state["last_user_response"] = state["messages"][-1].content

    conv_stage = state.get("conversation_stage", None)
    answered_questions = state.get("answered_questions", {})
        
    if not conv_stage:
        state["conversation_stage"] = ConversationStage.greeting
    elif conv_stage == ConversationStage.greeting:
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
            answered_questions["Domain"] = state["last_user_response"]
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

def greeting_node(state: AgentState, config: RunnableConfig) -> Dict:
    opening_message = greeting_prompt.invoke({"name": "AI Solution Architect."})
    output =  {"messages": [AIMessage(opening_message.text)]}
    return output 

def project_description_node(state: AgentState, config: RunnableConfig) -> Dict:
    project_description = prompt_description.invoke()
    output =  {"messages": [AIMessage(project_description.text)]}
    return output

def chatbot(state: AgentState) -> Dict[str, AnyMessage]:
    return {"messages": [llm.invoke(state["messages"])]}

def create_graph(checkpointer: AsyncPostgresSaver = None, memory: MemorySaver = None) -> StateGraph:
    """
    Creates the LangGraph graph.
    """
    graph = StateGraph(AgentState)  

    # Add nodes for different conversation stages
    graph.add_node("stage_update", stage_update)
    graph.add_node(ConversationStage.greeting.value, greeting_node)
    graph.add_node(ConversationStage.project_description.value, project_description_node)
    # graph.add_node("domain", lambda state: state)
    # graph.add_node("specify_goal", lambda state: state)
    # graph.add_node("pillar_questions", lambda state: state)
    # graph.add_node("summary", lambda state: state)

    # Build the graph structure
    graph.add_edge(
        START,
        "stage_update",
    )

    graph.add_edge(
        ConversationStage.greeting.value,
        END,
    )

    graph.add_edge(
        ConversationStage.project_description.value,
        END
    )
    graph.add_conditional_edges(
        "stage_update",
        route_step,
    )

    if memory:
        # Add a memory saver to the graph
        return graph.compile(memory)
    
    if checkpointer:
    # Compile
        return graph.compile(checkpointer=checkpointer)
    
    return graph.compile()


async def main():
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
        checkpointer = AsyncPostgresSaver(pool)

        graph = create_graph(checkpointer=checkpointer)

        config = {
            "configurable": {
                "conversation_id": "Test 10",
                "thread_id": "Test 10",
            }
        }
    

        res = await graph.ainvoke({"messages": [("human", "Hello")]}, config)
        checkpoint = await checkpointer.aget(config)
        print("=" * 50)

        for response in res["messages"]:
            print(response)
            print("=" * 50)

if __name__ == "__main__":
    # Run the main function in an asyncio event loop
    import asyncio
    import sys

    # Fix for Windows
    if sys.platform.startswith("win"):
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    asyncio.run(main())

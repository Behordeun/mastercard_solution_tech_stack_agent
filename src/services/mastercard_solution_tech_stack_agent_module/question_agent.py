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

from src.utilities.helpers import load_pillar_questions, load_yaml_file

from enum import Enum

# Fetch all prompts
greeting_prompt = load_prompt("src/services/mastercard_solution_tech_stack_agent_module/prompts/greeting.yaml")
prompt_description_prompt = load_prompt("src/services/mastercard_solution_tech_stack_agent_module/prompts/project_description.yaml")
domain_prompt = load_prompt("src/services/mastercard_solution_tech_stack_agent_module/prompts/domain.yaml")
specify_goal_prompt = load_prompt("src/services/mastercard_solution_tech_stack_agent_module/prompts/specify_goal.yaml")

# print(prompt_description_prompt)
pillar_questions = load_pillar_questions("src/services/mastercard_solution_tech_stack_agent_module/prompts/pillar_questions.yaml")

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

def greeting_node(state: AgentState, config: RunnableConfig) -> Dict:
    opening_message = greeting_prompt.invoke({"name": "AI Solution Architect."})
    output =  {"messages": [AIMessage(opening_message.text)]}
    return output 

def project_description_node(state: AgentState, config: RunnableConfig) -> Dict:
    project_description = prompt_description_prompt.invoke({"name": "AI Solution Architect."})
    output =  llm.invoke(state['messages'] + [AIMessage(project_description.text)])
    # print(output)
    return {"messages": output}

def domain_node(state: AgentState, config: RunnableConfig) -> Dict:
    domain = domain_prompt.invoke({"name": "AI Solution Architect."})
    output =  llm.invoke(state['messages'] + [AIMessage(domain.text)])
    return {"messages": output}

def specify_goal_node(state: AgentState, config: RunnableConfig) -> Dict:
    specify_goal = specify_goal_prompt.invoke({"name": "AI Solution Architect."})
    output =  llm.invoke(state['messages'] + [AIMessage(specify_goal.text)])
    return {"messages": output}


def _get_pillar_questions(state: AgentState) -> Dict:
        cur_pillar = state["current_pillar"]
        pillar_responses = state["pillar_responses"].get(cur_pillar, {})
        pillar_questions = pillar_questions[cur_pillar]
        print(pillar_responses)
        for question in pillar_questions:
            if question not in pillar_responses.keys():
                return state, question   

        # Check pillar is not in completed pillars
        if cur_pillar not in state["completed_pillars"]:
            state["completed_pillars"].append(cur_pillar)

        return state, None

def _start_pillar_questions(state: AgentState) -> Dict:
    state["current_pillar"] = _get_next_pillar(state)
    if state["current_pillar"]:
        state, question = _get_pillar_questions(state)

        if question == None:
            raise "Something is wrong"

        return (
            state,
            f"📋 Now let's discuss {state['current_pillar'].replace('_', ' ').title()} requirements... \n {question}"
        )

def _next_pillar_question(state: AgentState) -> Dict:
    print(state["pillar_responses"])
    if state["current_pillar"]:
        state, question = _get_pillar_questions(state)

        # If there are no more question for that pillar
        if question == None:
            return _start_pillar_questions(state)

        return (
            state,
            f"{question}"
        )
    return self._generate_summary(state)

def _save_pillar_response(state: AgentState) -> Dict:
    question = _get_pillar_questions(state)[1]
    cur_pillar = state["current_pillar"]
    # print(question)
    if cur_pillar:
        pillar_repsonses = state['pillar_responses'].get(cur_pillar, {})
        pillar_repsonses[question] = state['last_user_response']
        state["pillar_responses"][cur_pillar] = pillar_repsonses
        return state
    else:
        raise "Error"
    

def _get_next_pillar(state: AgentState) -> Optional[str]:
    for pillar in pillar_questions.keys():
        if pillar not in state["completed_pillars"]:
            return pillar
    return None

def pillar_questions_node(state: AgentState, config: RunnableConfig) -> Dict:
    # Placeholder for the pillar questions node
    state = _save_pillar_response(state)
    return _next_pillar_question(state)

def summary_node(state: AgentState, config: RunnableConfig) -> Dict:
    # Placeholder for the conversation stage node
    # You can implement the logic for this node as needed
    return {"messages": [AIMessage("What is the current conversation stage?")]}

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
    graph.add_node(ConversationStage.domain.value, domain_node)
    graph.add_node(ConversationStage.specify_goal.value, specify_goal_node)
    graph.add_node(ConversationStage.pillar_questions.value, pillar_questions_node)
    graph.add_node(ConversationStage.summary.value, summary_node)
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
    import random
    # test_sample = random.randint(1, 1000)
    test_sample = 758

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
                "conversation_id": f"Test {test_sample}",
                "thread_id": f"Test {test_sample}",
            }
        }

        print(config)

        res = await graph.ainvoke({"messages": [("human", "I am buidling a chatbot for family planning")]}, config)
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

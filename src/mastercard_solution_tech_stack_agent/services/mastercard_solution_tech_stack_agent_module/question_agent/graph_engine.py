from langgraph.checkpoint.memory import MemorySaver
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from langgraph.graph import END, START, StateGraph


from .nodes import (
    craft_question_node,
    greeting_node,
    pillar_questions_marker_node,
    pillar_questions_node,
    summary_node,
)
from .prompts import domain_prompt, prompt_description_prompt
from .utils import AgentState, ConversationStage, domain_knowledge_manager


def stage_update(state: AgentState):
    """
    Updates the state of the conversation based on the current stage.
    """
    # Logic to update the state based on the current stage
    state["user_interaction_count"] = state.get("user_interaction_count", 0) + 1
    state["last_message"] = state["messages"][-1].content if state["messages"] else None

    if state["messages"][-1].type == "human":
        state["last_user_response"] = state["messages"][-1].content

    conv_stage = state.get("conversation_stage", None)
    answered_questions = state.get("answered_questions", {})

    if not conv_stage:
        conv_stage = ConversationStage.greeting
    elif conv_stage and state.get("last_user_response") is not None:
        if conv_stage == ConversationStage.greeting:
            answered_questions["Goal"] = state["last_user_response"]
            conv_stage = ConversationStage.project_description
        elif conv_stage == ConversationStage.project_description:
            answered_questions["Project Description"] = state["last_user_response"]
            conv_stage = ConversationStage.domain
        elif conv_stage == ConversationStage.domain:
            answered_questions["Domain"] = state["last_user_response"]
            state["done_pillar_step"] = False
            conv_stage = ConversationStage.pillar_questions
        elif conv_stage == ConversationStage.specify_goal:
            answered_questions["Specify Goal"] = state["last_user_response"]
            state["done_pillar_step"] = False
            conv_stage = ConversationStage.pillar_questions
        elif conv_stage == ConversationStage.pillar_questions:
            if state["done_pillar_step"] == False:
                conv_stage = ConversationStage.pillar_questions
            else:
                answered_questions["Domain"] = state["last_user_response"]
                conv_stage = ConversationStage.summary
        elif conv_stage == ConversationStage.summary:
            if state["summary_confirmed"] == False:
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


def create_graph(
    checkpointer: AsyncPostgresSaver = None, memory: MemorySaver = None
) -> StateGraph:
    """
    Creates the LangGraph graph.
    """
    graph = StateGraph(AgentState)

    # Add nodes for different conversation stages
    graph.add_node("stage_update", stage_update)
    graph.add_node(ConversationStage.greeting.value, greeting_node)
    graph.add_node(
        ConversationStage.project_description.value,
        lambda state, config: craft_question_node(
            state=state, prompt=prompt_description_prompt
        ),
    )
    graph.add_node(
        ConversationStage.domain.value,
        lambda state, config: craft_question_node(
            state=state,
            prompt=domain_prompt,
            parameters={"domains": domain_knowledge_manager.knowledge},
        ),
    )
    graph.add_node(ConversationStage.pillar_questions.value, pillar_questions_node)
    graph.add_node("pillar_question_marker", pillar_questions_marker_node)
    graph.add_node(ConversationStage.summary.value, summary_node)

    # Build the graph structure
    graph.add_edge(
        START,
        "stage_update",
    )
    graph.add_edge(ConversationStage.greeting.value, END)
    graph.add_edge(ConversationStage.project_description.value, END)
    graph.add_edge(ConversationStage.domain.value, END)
    graph.add_edge(ConversationStage.pillar_questions.value, "pillar_question_marker")
    graph.add_edge("pillar_question_marker", END)

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
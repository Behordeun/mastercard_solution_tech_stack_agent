import os

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph

from services.mastercard_solution_tech_stack_agent_module.question_agent.nodes import (
    craft_question_node,
    greeting_node,
    pillar_questions_marker_node,
    pillar_questions_node,
    summary_node,
)
from services.mastercard_solution_tech_stack_agent_module.question_agent.utils import (
    AgentState,
    ConversationStage,
    domain_knowledge_manager,
)
from utilities.prompt_loader import (
    load_prompt_template_from_yaml,
)

# === Prompt File Paths ===
PROMPT_DIR = "services/mastercard_solution_tech_stack_agent_module/prompts"

domain_prompt = load_prompt_template_from_yaml(os.path.join(PROMPT_DIR, "domain.yaml"))
prompt_description_prompt = load_prompt_template_from_yaml(
    os.path.join(PROMPT_DIR, "project_description.yaml")
)
# specify_goal_prompt = load_prompt_template_from_yaml(os.path.join(PROMPT_DIR, "specify_goal.yaml"))


# === Stage Update Logic ===
def stage_update(state: AgentState):
    state["user_interaction_count"] = state.get("user_interaction_count", 0) + 1
    state["last_message"] = state["messages"][-1].content if state["messages"] else None

    if state["messages"][-1].type == "human":
        state["last_user_response"] = state["messages"][-1].content

    conv_stage = state.get("conversation_stage", ConversationStage.greeting)
    answered_questions = state.get("answered_questions", {})

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
    elif conv_stage == ConversationStage.pillar_questions:
        if state.get("done_pillar_step"):
            conv_stage = ConversationStage.summary
    elif conv_stage == ConversationStage.summary:
        if state.get("summary_confirmed", False):
            conv_stage = ConversationStage.end_of_conversation

    state["answered_questions"] = answered_questions
    state["conversation_stage"] = conv_stage
    return state


# === Router Step Logic ===
def route_step(state: AgentState):
    conv_stage = state.get("conversation_stage")
    return (
        conv_stage.value
        if conv_stage and conv_stage != ConversationStage.end_of_conversation
        else END
    )


# === Domain Prompt Node (lazy loading at runtime) ===
def domain_node(state, config):
    return craft_question_node(
        state, domain_prompt, parameters={"domains": domain_knowledge_manager.knowledge}
    )


# === Graph Creation ===
def create_graph(memory: MemorySaver = None):
    graph = StateGraph(AgentState)

    # Add all nodes
    graph.add_node("stage_update", stage_update)
    graph.add_node(ConversationStage.greeting.value, greeting_node)
    graph.add_node(
        ConversationStage.project_description.value,
        lambda s, c: craft_question_node(s, prompt_description_prompt),
    )
    graph.add_node(ConversationStage.domain.value, domain_node)
    graph.add_node(ConversationStage.pillar_questions.value, pillar_questions_node)
    graph.add_node("pillar_question_marker", pillar_questions_marker_node)
    graph.add_node(ConversationStage.summary.value, summary_node)

    # Edges
    graph.add_edge(START, "stage_update")
    graph.add_edge(ConversationStage.pillar_questions.value, "pillar_question_marker")
    graph.add_edge("pillar_question_marker", END)

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

    return graph.compile(memory)

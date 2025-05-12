from typing import Dict

from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.runnables import RunnableConfig
from langgraph.graph.message import AnyMessage

from src.mastercard_solution_tech_stack_agent.services.mastercard_solution_tech_stack_agent_module.question_agent.prompts import (
    greeting_prompt,
    pillar_marker_parser,
    pillar_marker_prompt_template,
    pillar_questions,
)
from src.mastercard_solution_tech_stack_agent.services.mastercard_solution_tech_stack_agent_module.question_agent.utils import (
    AgentState,
)
from src.mastercard_solution_tech_stack_agent.services.model import agent_model as llm


def question_marker(state: AgentState, config: RunnableConfig) -> Dict:
    """
    Moves through the responses and check the questions that has been answered by the user.
    It updates the state with the answered questions and the current pillar.
    """
    # Placeholder for the question marker stage
    # You can implement the logic for this node as needed
    return {"messages": [AIMessage("What is the current question marker?")]}


def greeting_node(state: AgentState, config: RunnableConfig) -> Dict:
    opening_message = greeting_prompt.invoke({"name": "AI Solution Architect."})
    return {"messages": [AIMessage(opening_message.to_string())]}


def craft_question_node(state, prompt, config=None, parameters=None):
    if parameters is None:
        parameters = {}

    # Merge answered questions with override parameters
    full_params = {
        **state.get("answered_questions", {}),
        **parameters
    }
    formatted_prompt = prompt.invoke(full_params)
    prompt_messages = formatted_prompt.to_messages()

    output = llm.invoke(state["messages"] + prompt_messages)
    return {"messages": state["messages"] + prompt_messages + [output]}


def pillar_questions_marker_node(state: AgentState, config: RunnableConfig) -> Dict:
    current_pillar = state.get("current_pillar", None)
    if state.get("pillar_responses", None) is None:
        state["pillar_responses"] = {}

    if current_pillar is None:
        return {"messages": [AIMessage("No current pillar to mark.")]}

    if state["pillar_responses"].get(current_pillar, None) is None:
        state["pillar_responses"][current_pillar] = {}

    cur_pillar_questions = pillar_questions.get(current_pillar, [])

    for question in cur_pillar_questions:
        if question not in state["pillar_responses"][current_pillar]:
            pillar_marker = pillar_marker_prompt_template.invoke({"question": question})
            output = llm.invoke(
                state["messages"] + [HumanMessage(pillar_marker.to_string())]
            )
            parsed_output = pillar_marker_parser.invoke(output)
            if parsed_output.get("answer_ready"):
                state["pillar_responses"][current_pillar][question] = parsed_output[
                    "answer"
                ]
            else:
                state["messages"].append(AIMessage(parsed_output["question"]))
                return state
    return state


def pillar_questions_node(state: AgentState, config: RunnableConfig) -> Dict:
    completed_pillars = state.get("completed_pillars", [])
    for pillar, questions in pillar_questions.items():
        if pillar not in completed_pillars:
            state["current_pillar"] = pillar
            return state
    # If all pillars are completed, move to summary
    completed_pillars.append(state["current_pillar"])
    state["completed_pillars"] = completed_pillars
    state["current_pillar"] = None
    state["messages"].append(
        AIMessage("All pillars have been completed. Moving to summary.")
    )
    return state


def summary_node(state: AgentState, config: RunnableConfig) -> Dict:
    # Placeholder for the conversation stage node
    # You can implement the logic for this node as needed
    return {"messages": [AIMessage("What is the current conversation stage?")]}


def chatbot(state: AgentState) -> Dict[str, AnyMessage]:
    return {"messages": [llm.invoke(state["messages"])]}

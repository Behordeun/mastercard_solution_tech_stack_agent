from typing import Dict

from langchain_core.exceptions import OutputParserException
from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.runnables import RunnableConfig
from langgraph.graph.message import AnyMessage

from src.mastercard_solution_tech_stack_agent.error_trace.errorlogger import (
    system_logger,
)
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
    return {"messages": [AIMessage("What is the current question marker?")]}


def greeting_node(state: AgentState, config: RunnableConfig) -> Dict:
    opening_message = greeting_prompt.invoke({"name": "AI Solution Architect."})
    return {"messages": [AIMessage(opening_message.to_string())]}


def craft_question_node(state, prompt, config=None, parameters=None):
    if parameters is None:
        parameters = {}

    full_params = {**state.get("answered_questions", {}), **parameters}
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
            # Add instruction to ensure JSON output is valid
            prompt_input = {
                "question": question,
                "format_instruction": 'Please return a valid JSON object with double-quoted keys. Example: { "answer_ready": false, "answer": "", "question": "..." }',
            }

            pillar_marker = pillar_marker_prompt_template.invoke(prompt_input)
            output = llm.invoke(
                state["messages"] + [HumanMessage(pillar_marker.to_string())]
            )

            try:
                parsed_output = pillar_marker_parser.invoke(output)
            except OutputParserException as e:
                system_logger.error(
                    e,
                    additional_info={
                        "context": "pillar_questions_marker_node",
                        "raw_output": str(output.content),
                    },
                    exc_info=True,
                )

                state["messages"].append(
                    AIMessage(
                        "Oops, I encountered a formatting issue. Let's try that question again."
                    )
                )
                return state

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

    completed_pillars.append(state["current_pillar"])
    state["completed_pillars"] = completed_pillars
    state["current_pillar"] = None
    state["messages"].append(
        AIMessage("All pillars have been completed. Moving to summary.")
    )
    return state


def summary_node(state: AgentState, config: RunnableConfig) -> Dict:
    return {"messages": [AIMessage("What is the current conversation stage?")]}


def chatbot(state: AgentState) -> Dict[str, AnyMessage]:
    return {"messages": [llm.invoke(state["messages"])]}

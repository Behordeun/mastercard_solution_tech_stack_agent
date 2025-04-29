from .utils import AgentState, ConversationStage
from .prompts import greeting_prompt, pillar_questions
from langgraph.graph.message import AnyMessage

from src.services.model import agent_model as llm

from typing import Dict
from langchain_core.runnables import RunnableConfig
from langchain_core.messages import AIMessage

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
    output =  {"messages": [AIMessage(opening_message.text)]}
    return output 


def craft_question_node(state, prompt, config = None, parameters = {}):
    formated_prompt = prompt.invoke(parameters)
    output =  llm.invoke(state['messages'] + [AIMessage(formated_prompt.text)])
    return {"messages": output}

def pillar_questions_marker_node(state: AgentState, config: RunnableConfig) -> Dict:
    pass

def pillar_questions_gen_node(state: AgentState, config: RunnableConfig) -> Dict:
    pass

def pillar_questions_node(state: AgentState, config: RunnableConfig) -> Dict:
    """
    Handles the pillar questions stage of the conversation.
    """
    if state['current_pillar'] is None:
        state['current_pillar'] = list(pillar_questions.keys())[0]
    
    if state['current_pillar'] in pillar_questions:
        question = pillar_questions[state['current_pillar']]
        output = llm.invoke(state['messages'] + [AIMessage(question)])
        return {"messages": output}
    
    # If all pillars are completed, move to summary
    state['completed_pillars'].append(state['current_pillar'])
    state['current_pillar'] = None
    return {"messages": [AIMessage("All pillars have been completed. Moving to summary.")]}

def summary_node(state: AgentState, config: RunnableConfig) -> Dict:
    # Placeholder for the conversation stage node
    # You can implement the logic for this node as needed
    return {"messages": [AIMessage("What is the current conversation stage?")]}

def chatbot(state: AgentState) -> Dict[str, AnyMessage]:
    return {"messages": [llm.invoke(state["messages"])]}
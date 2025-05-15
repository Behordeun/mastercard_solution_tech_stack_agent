from langchain_core.prompts import PromptTemplate
from src.mastercard_solution_tech_stack_agent.services.model import agent_model as llm


summarization_prompt = """
You are a Summarization Agent tasked with extracting the user's intent from a conversation they had with another agent.

The goal is to understand the user's background needs and objectives.
In this context, the user is seeking guidance on the appropriate tech stack for their problem domain. They express their needs in natural language.

Your task is to read the conversation and summarize the user's intent and technical requirements in a clear, coherent paragraph.

User Conversation: {conversation}

Please return the output in the following JSON format:

{{
  "conversation": "Summary of the user's intent and technical requirements"
}}
"""
summirization_prompt_template = PromptTemplate.from_template(summarization_prompt)

def get_conversation_summary(conversation: str) -> str:
    messages = summirization_prompt_template.invoke({"conversation": conversation})
    response = llm.invoke(messages)
    return response.content
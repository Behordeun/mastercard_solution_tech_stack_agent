from langchain_core.output_parsers import JsonOutputParser
from langchain_core.prompts import PromptTemplate
from pydantic import BaseModel, Field
from services.model import agent_model as llm

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


class SummarizedOutput(BaseModel):
    conversation: str = Field(
        description="Summary of the user's intent and technical requirements"
    )


parser = JsonOutputParser(pydantic_object=SummarizedOutput)

summirization_prompt_template = PromptTemplate.from_template(summarization_prompt)


def get_conversation_summary(conversation: str) -> str:
    chain = summirization_prompt_template | llm | parser

    response = chain.invoke({"conversation": conversation})
    return response

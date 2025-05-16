from typing import List, TypedDict

from langchain_core.documents import Document
from langchain_core.output_parsers import JsonOutputParser
from langchain_core.prompts import PromptTemplate
from langgraph.graph import START, StateGraph
from pydantic import BaseModel
from src.mastercard_solution_tech_stack_agent.services.model import agent_model as llm
from src.mastercard_solution_tech_stack_agent.utilities.vectorstore_builder import get_vectorstore

from .prompts import RECOMMENDER_PROMPT, REQUIREMENTS_PROMPT

vector_store = get_vectorstore()

recommender_prompt_template = PromptTemplate.from_template(RECOMMENDER_PROMPT)
requirement_prompt_template = PromptTemplate.from_template(REQUIREMENTS_PROMPT)


# Define state for application
class State(TypedDict):
    summary: str
    context: List[Document]
    requirements: str
    answer: str


from pydantic import BaseModel


class Recommendation(BaseModel):
    technology: str
    use_case: str


class FrontendRecommendation(BaseModel):
    top_recommendation: Recommendation
    alternative: Recommendation


class BackendRecommendation(BaseModel):
    top_recommendation: Recommendation
    alternative: Recommendation


class TechStackRecommendations(BaseModel):
    Frontend_Language: FrontendRecommendation
    Backend_Language: BackendRecommendation


parser = JsonOutputParser(pydantic_object=TechStackRecommendations)


# Define application steps
def retrieve(state: State):
    result_data = [
        vector_store.similarity_search(
            state["requirements"], k=10, filter={"Entity Type": entity}
        )
        for entity in ["Language", "Framework / Libraries", "Database", "Infastructure"]
    ]
    retrieved_docs = [
        "\n\n".join([i.page_content for i in data]) for data in result_data
    ]
    return {"context": retrieved_docs}


def get_requirements(state: State):
    messages = requirement_prompt_template.invoke({"requirements": state["summary"]})
    response = llm.invoke(messages)
    return {"requirements": response.content}


def generate(state: State):
    docs_content = "\n\n".join(doc for doc in state["context"])
    messages = recommender_prompt_template.invoke(
        {
            "requirements": state["requirements"],
            "context": docs_content,
            "question": state["summary"],
        }
    )
    response = llm.invoke(messages)
    return {"answer": response.content}


def recommend_teck_stack(messages, user_query):
    # Compile application and test
    graph_builder = StateGraph(State).add_sequence(
        [get_requirements, retrieve, generate]
    )
    graph_builder.add_edge(START, "get_requirements")
    graph = graph_builder.compile()
    result = graph.invoke({"summary": user_query})
    return parser.invoke(result["answer"])

from langchain_chroma import Chroma
from langchain_core.documents import Document
from typing import TypedDict, List


# Define state for application
class State(TypedDict):
    question: str
    context: List[Document]
    requirements: str
    answer: str


# Define application steps
def retrieve(state: State):

    result_data = [vector_store.similarity_search(state["requirements"], k=10, filter={"Entity Type": entity}) for entity in ["Language", "Framework / Libraries", "Database", "Infastructure"]]


    retrieved_docs = ["\n\n".join([i.page_content for i in data ]) for data in result_data]


    return {"context": retrieved_docs}


def get_requirements(state: State):
    messages = requirements_prompt.invoke({"requirements": state["question"]})
    response = llm.invoke(messages)
    return {"requirements": response.content}

def generate(state: State):
    docs_content = "\n\n".join(doc for doc in state["context"])
    messages = generation_prompt.invoke({"requirements": state["requirements"], "context": docs_content, "question":state["question"]})
    response = llm.invoke(messages)
    return {"answer": response.content}


# Compile application and test
graph_builder = StateGraph(State).add_sequence([get_requirements, retrieve, generate])
graph_builder.add_edge(START, "get_requirements")
graph = graph_builder.compile()
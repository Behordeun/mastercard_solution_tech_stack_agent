from typing import List
from langchain_community.document_loaders import TextLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import FAISS
from langchain_openai import OpenAIEmbeddings

from langchain_chroma import Chroma
from langchain_core.documents import Document
from langchain_huggingface import HuggingFaceEmbeddings

import pandas as pd
import os


def build_faiss_vectorstore(
    input_paths: List[str],
    persist_path: str = "src/services/techstack_agent_module/kb_vectorstore",
    chunk_size: int = 500,
    chunk_overlap: int = 100,
):
    documents = []
    for path in input_paths:
        loader = TextLoader(path)
        documents += loader.load()

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size, chunk_overlap=chunk_overlap
    )
    chunks = splitter.split_documents(documents)

    embeddings = OpenAIEmbeddings()
    vectorstore = FAISS.from_documents(chunks, embeddings)
    vectorstore.save_local(persist_path)


# Tech Stack Recommender Agent VectorDB (Use Chroma because of metadata filtering support)
# knowledge base path

CURRENT_DIR = os.path.dirname(__file__)
# the mastercard_solution_tech_stack_agent_module dir
BASE_DIR = os.path.abspath(os.path.join(CURRENT_DIR, "..", "services", "mastercard_solution_tech_stack_agent_module"))

print(f"BASE_DIR: {BASE_DIR}")
def get_vectorstore():
    vectordb_path = os.path.join(BASE_DIR, "kb_vectorstore", "chroma")

    kb_path = os.path.join(vectordb_path, "Tech Stack.csv")

    # initalize embedding model
    embeddings = HuggingFaceEmbeddings(model_name="sentence-transformers/all-mpnet-base-v2")

    if os.path.exists(vectordb_path):
        vector_store = Chroma(
            persist_directory=vectordb_path,
            embedding_function=embeddings
        )
        return vector_store

    if os.path.exists(kb_path):
        kb_data = pd.read_csv(kb_path)

        # structure each record to be in a single string and have metadata attached.
        kb_result = [
            Document(
                page_content=", ".join([f"{col}: {d[col]}" for col in kb_data.columns]),
                metadata=dict(
                    zip(
                        ["Entity Type", "Entity Category", "Entity Sub Category"],
                        [d["Entity Type"], d["Entity Category"], d["Entity Sub Category"]]
                    )
                )
            )
            for _, d in kb_data.iterrows()
        ]

        vector_store = Chroma.from_documents(
            documents=kb_result,
            embedding=embeddings,
            persist_directory=vectordb_path)
        
        return vector_store   
    else:
        raise FileNotFoundError(f"Vectorstore path {vectordb_path} does not exist.")

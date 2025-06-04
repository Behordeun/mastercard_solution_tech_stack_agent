import os
import chromadb
from typing import List, Optional

import pandas as pd
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_chroma import Chroma
from langchain_community.document_loaders import TextLoader
from langchain_community.vectorstores import FAISS
from langchain_core.documents import Document
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_openai import OpenAIEmbeddings

CURRENT_DIR = os.path.dirname(__file__)
# the mastercard_solution_tech_stack_agent_module dir
BASE_DIR = os.path.abspath(
    os.path.join(
        CURRENT_DIR, "..", "services", "mastercard_solution_tech_stack_agent_module"
    )
)

print(f"BASE_DIR: {BASE_DIR}")

# # Initialize Vector db
# if Settings.Embedding.USE_HTTP_CLIENT:
#     print("Using Online Client")
#     vector_db = chromadb.HttpClient(host=Settings.Embedding.HTTP_CLIENT, 
#                                 port=Settings.Embedding.HTTP_PORT)
# else:
#     print("Using Local Client")
vector_db = chromadb.PersistentClient(path="./chroma_db")

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

def create_vectorstore(embeddings, collection_name, vectordb_path : str = os.path.join(BASE_DIR, "kb_vectorstore", "chroma"), kb_path: Optional[str] = None,):
    # Initialize kbpath
    if kb_path:
        kb_path = os.path.join(vectordb_path, "Tech Stack.csv")

    if os.path.exists(kb_path):
        kb_data = pd.read_csv(kb_path)

        # structure each record to be in a single string and have metadata attached.
        kb_result = [
            Document(
                page_content=", ".join([f"{col}: {d[col]}" for col in kb_data.columns]),
                metadata=dict(
                    zip(
                        kb_data.columns,
                        [d[col] for col in kb_data.columns],
                    )
                ),
            )
            for _, d in kb_data.iterrows()
        ]

        vector_store = Chroma.from_documents(
            documents=kb_result, embedding=embeddings, persist_directory=vectordb_path, collection_name=collection_name
        )

        return vector_store

# def get_vectorstore(
#     kb_path: Optional[str] = None,
#     vectordb_path : str = os.path.join(BASE_DIR, "kb_vectorstore", "chroma"),
#     model_name: str ="sentence-transformers/all-mpnet-base-v2"
# ):
#     # Initialize vectorstore persistent path
#     vectordb_path : str = os.path.join(BASE_DIR, "kb_vectorstore", "chroma"),
    
#     # Initialize kbpath
#     if kb_path:
#         kb_path = os.path.join(vectordb_path, "Tech Stack.csv")

#     # initalize embedding model
#     embeddings = HuggingFaceEmbeddings( model_name=model_name)

#     if os.path.exists(vectordb_path):
#         os.makedirs(vectordb_path, exist_ok=True)

#         vector_store = vector_db.get_collection("syllabus", embedding_function=embeddings) 

#         return vector_store

#     if os.path.exists(kb_path):
#         kb_data = pd.read_csv(kb_path)

#         # structure each record to be in a single string and have metadata attached.
#         kb_result = [
#             Document(
#                 page_content=", ".join([f"{col}: {d[col]}" for col in kb_data.columns]),
#                 metadata=dict(
#                     zip(
#                         ["Entity Type", "Entity Category", "Entity Sub Category"],
#                         [d[col] for col in kb_data.columns],
#                     )
#                 ),
#             )
#             for _, d in kb_data.iterrows()
#         ]

#         vector_store = Chroma.from_documents(
#             documents=kb_result, embedding=embeddings, persist_directory=vectordb_path
#         )

#         return vector_store
#     else:
#         raise FileNotFoundError(f"Vectorstore path {vectordb_path} does not exist.")

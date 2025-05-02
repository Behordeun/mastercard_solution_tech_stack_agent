from typing import List
from langchain_chroma import Chroma
from langchain_core.documents import Document
from langchain_huggingface import HuggingFaceEmbeddings

import pandas as pd
import os

# def build_faiss_vectorstore(
#     input_paths: List[str],
#     persist_path: str = "src/services/techstack_agent_module/kb_vectorstore",
#     chunk_size: int = 500,
#     chunk_overlap: int = 100,
# ):
#     documents = []
#     for path in input_paths:
#         loader = TextLoader(path)
#         documents += loader.load()

#     splitter = RecursiveCharacterTextSplitter(
#         chunk_size=chunk_size, chunk_overlap=chunk_overlap
#     )
#     chunks = splitter.split_documents(documents)

#     embeddings = OpenAIEmbeddings()
#     vectorstore = FAISS.from_documents(chunks, embeddings)
#     vectorstore.save_local(persist_path)


# Using Chroma Vector DB Instead

# knowledge base path

CURRENT_DIR = os.path.dirname(__file__)
BASE_DIR = os.path.abspath(os.path.join(CURRENT_DIR, ".."))


def get_vectorstore():

    vectordb_path = os.path.join(BASE_DIR, "services", "kb_vectorstore", "chroma")
    # initalize embedding model

    print(vectordb_path)
    embeddings = HuggingFaceEmbeddings(model_name="sentence-transformers/all-mpnet-base-v2")


    if os.path.exists(kb_path):

        vector_store = Chroma(
            persist_directory=vectordb_path,
            embedding_function=embeddings
        )
        return vector_store

    kb_path = os.path.join("docs", "Tech Stack.csv")

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

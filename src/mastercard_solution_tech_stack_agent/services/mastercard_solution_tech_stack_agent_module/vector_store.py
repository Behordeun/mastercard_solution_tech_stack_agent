import os
import pandas as pd

from chromadb import PersistentClient

from langchain_chroma import Chroma
from langchain_core.documents import Document
from langchain_huggingface import HuggingFaceEmbeddings

from src.mastercard_solution_tech_stack_agent.config.settings import settings
from src.mastercard_solution_tech_stack_agent.utilities.vectorstore_builder import vector_db, create_vectorstore, BASE_DIR
from src.mastercard_solution_tech_stack_agent.services.mastercard_solution_tech_stack_agent_module.agent_config import MasterCardAgentConfig

embeddings = HuggingFaceEmbeddings(model_name=MasterCardAgentConfig.EMBED_MODEL)
client = PersistentClient(path = "./chroma")

def create_project_vectorstore(embeddings = embeddings, collection_name = MasterCardAgentConfig.PREVIOUS_PROJECT_COLLECTION_NAME) -> Chroma:
    if os.path.exists(MasterCardAgentConfig.PREVIOUS_PROJECT_PATH):
        kb_data = pd.read_csv(MasterCardAgentConfig.PREVIOUS_PROJECT_PATH)

        # structure each record to be in a single string and have metadata attached.
        kb_result = [
            Document(
                page_content=f"Project Title: {d['Project Title']} \nProject Description: {d['Project Description']}",
                metadata=dict(
                    zip(
                        kb_data.columns,
                        [d[col] for col in kb_data.columns],
                    )
                ),
            )
            for _, d in kb_data.iterrows()
        ]

        vector_store = Chroma.from_documents(documents=kb_result, embedding=embeddings, client=client, collection_name=collection_name)

        return vector_store
    
def create_techstack_vectorstore(embeddings = embeddings, collection_name = MasterCardAgentConfig.TECHSTACK_COLLECTION_NAME) -> Chroma:
    if os.path.exists(MasterCardAgentConfig.TECH_STACK_FILE):
        kb_data = pd.read_csv(MasterCardAgentConfig.TECH_STACK_FILE)

        # structure each record to be in a single string and have metadata attached.
        kb_result = [
            Document(
                page_content=", ".join([f"{col}: {d[col]}" for col in ["Entity Sub Category","Description","License","Language Compatibility"]]),
                metadata=dict(
                    zip(
                        kb_data.columns,
                        [d[col] for col in kb_data.columns],
                    )
                ),
            )
            for _, d in kb_data.iterrows()
        ]

        vector_store = Chroma.from_documents(documents=kb_result, embedding=embeddings, client=client, collection_name=collection_name)

        return vector_store
        
def get_project_vectordb():
    collection = vector_db.list_collections()
    if MasterCardAgentConfig.PROJECT_VECTORDB_NAME in collection:
        project_vector_store = Chroma(collection_name=MasterCardAgentConfig.PROJECT_VECTORDB_NAME, 
                                      embedding_function=embeddings)
    else:
        project_vector_store = create_project_vectorstore()
    
    return project_vector_store

def get_techstack_vectordb():
    collection = vector_db.list_collections()
    if MasterCardAgentConfig.TECHSTACK_VECTORDB_NAME in collection:
        techstack_vector_store = Chroma(collection_name=MasterCardAgentConfig.TECHSTACK_VECTORDB_NAME, 
                                      embedding_function=embeddings)
    else:
        techstack_vector_store = create_techstack_vectorstore(embeddings=embeddings, 
                                                  collection_name=MasterCardAgentConfig.TECHSTACK_VECTORDB_NAME)
    
    return techstack_vector_store  

project_vectordb = get_project_vectordb()
techstack_vectordb = get_techstack_vectordb()
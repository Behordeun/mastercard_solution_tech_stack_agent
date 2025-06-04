import os
from pydantic_settings import BaseSettings

CURRENT_DIR = os.path.dirname(__file__)

class MasterCardAgentConfig(BaseSettings):
    """Class to hold for the mastercard agent"""
    PROJECT_VECTORDB_NAME = "Project Vectordb"
    TECHSTACK_VECTORDB_NAME = "TechStack Vectordb"
    EMBED_MODEL = "sentence-transformers/all-mpnet-base-v2"

    DATA_FOLDER: str = "data"
    DATA_DIR: str = os.path.abspath(os.path.join(CURRENT_DIR, DATA_FOLDER))

    TECH_STACK_FILE: str = "Tech Stack.csv"
    TECHSTACK_COLLECTION_NAME: str = "Tech Stack"
    TECH_STACK_PATH: str = os.path.abspath(os.path.join(DATA_DIR, TECH_STACK_FILE))

    PREVIOUS_PROJECT_FILE: str = "Previous Project.csv"
    PREVIOUS_PROJECT_COLLECTION_NAME: str = "Previous Project"
    PREVIOUS_PROJECT_PATH: str = os.path.abspath(os.path.join(DATA_DIR, PREVIOUS_PROJECT_FILE))

    PILLAR_QUESTION_FOLDER: str = "Pillar Questions"
    PILLAR_QUESTION_PATH: str = os.path.abspath(os.path.join(DATA_DIR, PILLAR_QUESTION_FOLDER))
    
    pillar_question: dict = {
        "Agriculture Pillar 2": os.path.abspath(os.path.join(PILLAR_QUESTION_PATH, "Agriculture_sample_2.csv")), 
        "Agriculture Pillar 1": os.path.abspath(os.path.join(PILLAR_QUESTION_PATH, "Agriculture_sample_2.csv")), 
        "Finance Pillar 1": os.path.abspath(os.path.join(PILLAR_QUESTION_PATH, "Finance_sample.csv")), 
        "Health Pillar 1": os.path.abspath(os.path.join(PILLAR_QUESTION_PATH, "Health_sample.csv"))
    }
# libraries
import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, List

from langchain.chains import RetrievalQA
from langchain.tools import Tool
from langchain_community.vectorstores import FAISS
from langchain_openai import OpenAIEmbeddings

from src.mastercard_solution_tech_stack_agent.config.db_setup import SessionLocal
from src.mastercard_solution_tech_stack_agent.config.settings import Settings
from src.mastercard_solution_tech_stack_agent.services.model import agent_model as model

# === Log directory setup ===
LOG_DIR = "src/mastercard_solution_tech_stack_agent/logs"
os.makedirs(LOG_DIR, exist_ok=True)

# === Log file paths ===
LOG_FILES = {
    "info": os.path.join(LOG_DIR, "info.log"),
    "warning": os.path.join(LOG_DIR, "warning.log"),
    "error": os.path.join(LOG_DIR, "error.log"),
}

# === Logging format ===
log_format = logging.Formatter("%(asctime)s - %(levelname)s - %(name)s - %(message)s")

# === Set up handlers per log level ===
handlers = []
for level, path in LOG_FILES.items():
    handler = logging.FileHandler(path)
    handler.setLevel(getattr(logging, level.upper()))
    handler.setFormatter(log_format)
    handlers.append(handler)

# === Attach handlers to root logger ===
root_logger = logging.getLogger()
root_logger.setLevel(logging.INFO)
root_logger.handlers = []  # Remove existing
for h in handlers:
    root_logger.addHandler(h)
root_logger.addHandler(logging.StreamHandler())  # Console

logger = logging.getLogger(__name__)

settings = Settings()
db = SessionLocal()

DOMAIN_KNOWLEDGE_PATH = "src/mastercard_solution_tech_stack_agent/services/mastercard_solution_tech_stack_agent_module/data/domain_knowledge.json"
VECTORSTORE_PATH = "src/mastercard_solution_tech_stack_agent/services/mastercard_solution_tech_stack_agent_module/kb_vectorstore"

# @tool
# def null(data: Annotated[str, ""]) -> str:
#     pass


# === DOMAIN KNOWLEDGE MANAGEMENT ===
class DomainKnowledgeManager:
    def __init__(self, file_path: str):
        self.file_path = Path(file_path)
        self.file_path.parent.mkdir(parents=True, exist_ok=True)
        self.knowledge = self._load_knowledge()

    def _load_knowledge(self) -> Dict:
        try:
            if self.file_path.exists():
                with open(self.file_path, "r") as f:
                    return json.load(f)
        except (json.JSONDecodeError, Exception) as e:
            logger.warning(f"Error loading domain knowledge: {e}")

        return {
            "common_domains": [
                "Education",
                "Healthcare",
                "Finance",
                "E-commerce",
                "Agriculture",
                "Logistics",
            ],
            "custom_domains": [],
            "domain_insights": {},
            "last_updated": datetime.now().isoformat(),
        }

    def save_knowledge(self):
        try:
            with open(self.file_path, "w") as f:
                json.dump(self.knowledge, f, indent=2)
        except Exception as e:
            logger.error(f"Error saving domain knowledge: {e}")

    def add_domain(self, domain: str, insights: str = ""):
        domain = domain.strip()
        if not domain:
            return False

        domain_lower = domain.lower()
        existing_domains = (
            self.knowledge["common_domains"] + self.knowledge["custom_domains"]
        )

        if not any(d.lower() == domain_lower for d in existing_domains):
            self.knowledge["custom_domains"].append(domain)
            if insights:
                self.knowledge["domain_insights"][domain] = insights
            self.knowledge["last_updated"] = datetime.now().isoformat()
            self.save_knowledge()
            return True
        return False

    def get_domain_insights(self, domain: str) -> str:
        domain = domain.strip()
        return self.knowledge["domain_insights"].get(
            domain,
            "I'll analyze your specific requirements to provide tailored recommendations.",
        )

    def get_similar_domains(self, domain: str) -> List[str]:
        domain = domain.strip().lower()
        all_domains = (
            self.knowledge["common_domains"] + self.knowledge["custom_domains"]
        )
        return [d for d in all_domains if domain in d.lower()]


# === COMPONENT INITIALIZATION ===
domain_knowledge_manager = DomainKnowledgeManager(DOMAIN_KNOWLEDGE_PATH)


vectorstore = FAISS.load_local(
    str(VECTORSTORE_PATH),
    OpenAIEmbeddings(),
    allow_dangerous_deserialization=True,
)
retriever = vectorstore.as_retriever()
qa_chain = RetrievalQA.from_chain_type(llm=model, retriever=retriever)


tools = [
    Tool(
        name="KnowledgeBase",
        func=qa_chain.run,
        description="Use this to answer architecture, meta-guidance, and tech stack questions.",
    ),
    Tool(
        name="DomainExpert",
        func=lambda q: domain_knowledge_manager.get_domain_insights(q),
        description="Use this to get domain-specific insights and recommendations.",
    ),
]

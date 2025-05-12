from typing import Annotated, Dict, List, Optional
from langgraph.graph.message import AnyMessage, add_messages
from typing_extensions import TypedDict
from datetime import datetime
from pathlib import Path
from enum import Enum
import json
import logging

DOMAIN_KNOWLEDGE_PATH = "src/services/mastercard_solution_tech_stack_agent_module/data/domain_knowledge.json"

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class ConversationStage(Enum):
    greeting = "greeting"
    project_description = "project_description"
    domain = "domain"
    pillar_questions = "pillar_questions"
    specify_goal = "specify goal"
    summary = "summary"
    end_of_conversation = "end_of_conversation"

# === STATE ===
class AgentState(TypedDict):
    messages: Annotated[List[AnyMessage], add_messages]     # List of messages in the conversation 
    conversation_stage: ConversationStage                   # Current stage of the conversation
    user_interaction_count: int                             # Number of interactions with the user
    last_message: Optional[str]                             # Last message sent to the user
    last_user_response: Optional[str]                       # Last response from the user
    pillar_responses: Dict[str, Dict[str, str]]             # Responses to pillar questions
    answered_questions: Dict[str, str]                      # List of answered by the user, with question and answer pairs
    current_pillar: Optional[str]                           # Current pillar being discussed
    completed_pillars: List[str] = []                       # List of completed pillars
    done_pillar_step: bool = False                          # Whether the current pillar step is done
    summary_confirmed: bool                                 # Whether the summary has been confirmed by the user 


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

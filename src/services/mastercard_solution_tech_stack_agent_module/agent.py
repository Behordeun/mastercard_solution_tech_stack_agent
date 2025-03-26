import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Annotated, Dict, List, Optional, Tuple

from langchain.chains import RetrievalQA
from langchain.prompts import PromptTemplate
from langchain.tools import Tool
from langchain_community.vectorstores import FAISS
from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import Runnable, RunnableConfig, RunnableSequence
from langchain_openai import OpenAIEmbeddings
from langgraph.graph import START, StateGraph
from langgraph.graph.message import AnyMessage, add_messages
from langgraph.prebuilt import ToolNode, tools_condition
from typing_extensions import TypedDict

from src.services.model import agent_model as model
from src.utilities.helpers import load_pillar_questions, load_yaml_file

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# === CONFIG ===
PROMPT_PATH = "src/services/mastercard_solution_tech_stack_agent_module/prompts/instruction.yaml"
CSV_QUESTIONS_PATH = (
    "src/services/mastercard_solution_tech_stack_agent_module/data/Pillars and Key Questions-Final.csv"
)
VECTORSTORE_PATH = "src/services/mastercard_solution_tech_stack_agent_module/kb_vectorstore"
DOMAIN_KNOWLEDGE_PATH = "src/services/mastercard_solution_tech_stack_agent_module/data/domain_knowledge.json"


# === STATE ===
class State(TypedDict):
    messages: Annotated[List[AnyMessage], add_messages]
    user_interaction_count: int
    last_message: Optional[str]
    last_user_response: Optional[str]
    program_context: Dict[str, str]
    pillar_responses: Dict[str, Dict[str, str]]
    asked_questions: List[str]
    current_pillar: Optional[str]
    completed_pillars: List[str]
    summary_confirmed: bool
    recommended_stack: Optional[str]
    tech_stack_ready: bool


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


def _initialize_components():
    try:
        prompt_template = load_yaml_file(Path(PROMPT_PATH)).get("SYSTEMPROMPT", "")
        prompt = ChatPromptTemplate.from_messages(
            [
                ("system", prompt_template),
                ("placeholder", "{messages}"),
            ]
        )

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

        stack_prompt = PromptTemplate.from_template(
            """You are a senior solution architect. Based on:
- Initiative: "{initiative}"
- Domain: "{domain}"
- Requirements: {pillar_responses}

Generate a tailored, justified tech stack in markdown format with:
1. Core components table
2. Integration recommendations
3. Domain-specific considerations
4. Scalability advice"""
        )

        stack_generator = RunnableSequence(stack_prompt, model)

        return {
            "assistant_runnable": prompt | model.bind_tools(tools),
            "tools_to_use": tools,
            "pillar_questions": load_pillar_questions(CSV_QUESTIONS_PATH),
            "stack_generator": stack_generator,
        }
    except Exception as e:
        logger.error(f"Error initializing components: {e}")
        raise


components = _initialize_components()


# === AGENT CLASS ===
class Assistant:
    def __init__(self, runnable: Runnable, questions: Dict[str, List[str]]):
        self.runnable = runnable
        self.questions = questions
        self.stack_generator = components["stack_generator"]
        self.domain_manager = domain_knowledge_manager
        self.conversation_stage = "greeting"  # Tracks conversation progress

    def _initialize_state(self, state: State) -> State:
        defaults = {
            "user_interaction_count": 0,
            "last_message": None,
            "last_user_response": None,
            "program_context": {},
            "pillar_responses": {},
            "asked_questions": [],
            "current_pillar": None,
            "completed_pillars": [],
            "summary_confirmed": False,
            "recommended_stack": None,
            "tech_stack_ready": False,
        }
        for key in defaults:
            if key not in state:
                state[key] = defaults[key]
        return state

    def _push(self, state: State, message: str) -> Dict:
        try:
            msg = AIMessage(content=message)
            state["messages"].append(msg)
            state["last_message"] = message
            return {"message": msg, "messages": state["messages"]}
        except Exception as e:
            logger.error(f"Error pushing message: {e}")
            return state

    async def handle_domain_input(self, state: State) -> Tuple[Dict, bool]:
        """Process domain input with learning capability"""
        user_domain = state["last_user_response"].strip()
        if not user_domain:
            return (
                self._push(state, "🌍 Please specify a domain for your solution"),
                False,
            )

        is_new = self.domain_manager.add_domain(user_domain)
        state["program_context"]["domain"] = user_domain

        if is_new:
            similar = self.domain_manager.get_similar_domains(user_domain)
            similar_msg = f"Similar domains: {', '.join(similar)}" if similar else ""
            return (
                self._push(
                    state,
                    f"🌐 Added '{user_domain}' to our knowledge base!\n"
                    f"{similar_msg}\n\n"
                    f"{self.domain_manager.get_domain_insights(user_domain)}",
                ),
                True,
            )

        return (
            self._push(
                state,
                f"✅ Domain: {user_domain}\n"
                f"{self.domain_manager.get_domain_insights(user_domain)}",
            ),
            False,
        )

    async def run(self, state: State, config: RunnableConfig) -> Dict:
        try:
            state = self._initialize_state(state)
            messages = state["messages"]
            last_user_message = next(
                (m for m in reversed(messages) if isinstance(m, HumanMessage)), None
            )

            # Track conversation progress
            if last_user_message:
                state["last_user_response"] = last_user_message.content
                user_msg = last_user_message.content.lower()

                # Update conversation stage based on user input
                if self.conversation_stage == "greeting":
                    if any(greet in user_msg for greet in ["hi", "hello", "hey"]):
                        self.conversation_stage = "project_description"
                        return self._push(
                            state,
                            "Great! Let's begin with your project:\n\n"
                            "🧭 What are you building? (e.g., 'A patient management system', 'An educational platform')"
                        )
                    else:
                        # Treat as project description if not a greeting
                        self.conversation_stage = "project_description"
                        state["program_context"]["initiative"] = state["last_user_response"]
                        return self._ask_for_domain(state)

                elif self.conversation_stage == "project_description":
                    if not state["program_context"].get("initiative"):
                        state["program_context"]["initiative"] = state["last_user_response"]
                        return self._ask_for_domain(state)

                elif self.conversation_stage == "domain":
                    if not state["program_context"].get("domain"):
                        state["program_context"]["domain"] = state["last_user_response"]
                        self.conversation_stage = "pillar_questions"
                        return self._start_pillar_questions(state)

            # Initial greeting
            if self.conversation_stage == "greeting":
                self.conversation_stage = "awaiting_greeting_response"
                return self._push(
                    state,
                    "👋 Hello! I'm your AI Solution Architect. I specialize in designing optimal technology stacks.\n\n"
                    "Let's start with your project goal..."
                )

            # Handle empty state transitions
            if not state["program_context"].get("initiative"):
                return self._push(
                    state,
                    "🧭 What are you building? Describe your project in 1-2 sentences.\n"
                    "Examples:\n- 'A patient management system for clinics'\n"
                    "- 'An educational platform for K-12 students'"
                )

            if not state["program_context"].get("domain"):
                return self._ask_for_domain(state)

            # Continue with pillar questions
            return await self._continue_conversation(state)

        except Exception as e:
            logger.error(f"Error in run method: {e}")
            return self._push(state, "⚠️ Sorry, I encountered an error. Let me try again...")

    def _ask_for_domain(self, state: State) -> Dict:
        common_domains = self.domain_manager.knowledge["common_domains"]
        return self._push(
            state,
            "🌍 What industry/domain does this serve?\n"
            f"Common domains: {', '.join(common_domains)}\n"
            "Or specify your own:"
        )

    def _start_pillar_questions(self, state: State) -> Dict:
        state["current_pillar"] = self._get_next_pillar(state)
        if state["current_pillar"]:
            return self._push(
                state,
                f"📋 Now let's discuss {state['current_pillar'].replace('_', ' ').title()} requirements..."
            )
        return self._generate_summary(state)

    def _get_next_pillar(self, state: State) -> Optional[str]:
        for pillar in self.questions.keys():
            if pillar not in state["completed_pillars"]:
                return pillar
        return None

    def _generate_summary(self, state: State) -> Dict:
        summary = [
            "✅ Summary of your inputs:",
            f"- Project: {state['program_context'].get('initiative', 'N/A')}",
            f"- Domain: {state['program_context'].get('domain', 'N/A')}",
        ]
        for pillar, responses in state["pillar_responses"].items():
            summary.append(f"\n📋 {pillar.replace('_', ' ').title()}:")
            for q, a in responses.items():
                summary.append(f"• {q}: {a}")
        summary.append("\nDoes this look correct? (yes/no/edit)")
        return self._push(state, "\n".join(summary))

    async def _recommend_stack(self, state: State) -> Dict:
        last_input = state["messages"][-1].content.lower()
        if not state["summary_confirmed"]:
            if "yes" in last_input:
                state["summary_confirmed"] = True
            else:
                return self._push(state, "Please confirm the summary before we proceed")

        pillar_data = "\n".join(
            f"{p.replace('_', ' ').title()}:\n"
            + "\n".join(f"- {q}: {a}" for q, a in r.items())
            for p, r in state["pillar_responses"].items()
        )

        stack = await self.stack_generator.ainvoke(
            {
                "initiative": state["program_context"]["initiative"],
                "domain": state["program_context"]["domain"],
                "pillar_responses": pillar_data,
            }
        )

        state["recommended_stack"] = stack.content
        state["tech_stack_ready"] = True

        return self._push(
            state,
            f"🧱 Here's your tailored tech stack:\n\n{stack.content}\n\n"
            "Would you like to make any adjustments or need clarification?",
        )


# === Graph Setup ===
assistant = Assistant(
    runnable=components["assistant_runnable"], questions=components["pillar_questions"]
)


async def assistant_node(state: State, config: RunnableConfig) -> Dict:
    return await assistant.run(state, config)


def techstack_agent_graph():
    builder = StateGraph(State)
    builder.add_node("assistant", assistant_node)
    builder.add_node("tools", ToolNode(components["tools_to_use"]))
    builder.add_edge(START, "assistant")
    builder.add_conditional_edges("assistant", tools_condition)
    builder.add_edge("tools", "assistant")
    return builder.compile()


agent = techstack_agent_graph()

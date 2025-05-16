import logging
from enum import Enum
from pathlib import Path
from typing import Annotated, Dict, List, Optional, Tuple

from langchain.prompts import PromptTemplate
from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import Runnable, RunnableConfig
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import START, StateGraph
from langgraph.graph.message import AnyMessage, add_messages
from langgraph.prebuilt import ToolNode, tools_condition
from typing_extensions import TypedDict

from src.mastercard_solution_tech_stack_agent.services.mastercard_solution_tech_stack_agent_module.toolskit import (
    domain_knowledge_manager, tools)
from src.mastercard_solution_tech_stack_agent.services.model import \
    agent_model as model
from src.mastercard_solution_tech_stack_agent.utilities.helpers import (
    load_pillar_questions, load_yaml_file)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# === CONFIG ===
PROMPT_PATH = (
    "services/mastercard_solution_tech_stack_agent_module/prompts/instruction.yaml"
)
STACK_PROMPT_PATH = (
    "services/mastercard_solution_tech_stack_agent_module/prompts/stack_prompt.yaml"
)

CSV_QUESTIONS_PATH = "services/mastercard_solution_tech_stack_agent_module/data/Sample Pillars and Key Questions-Final copy.csv"

# CSV_QUESTIONS_PATH = "services/mastercard_solution_tech_stack_agent_module/data/Sample Pillars and Key Questions-Final copy.csv"

prompt_template = load_yaml_file(Path(PROMPT_PATH))


class ConversationStage(Enum):
    greeting = "greeting"
    project_description = "project_description"
    domain = "domain"
    pillar_questions = "pillar_questions"
    awaiting_greeting_response = "awaiting_greeting_response"
    specify_goal = "specify goal"
    generate_summary = "generate summary"
    recommend_stack = "recommend stack"


# === STATE ===
class State(TypedDict):
    messages: Annotated[List[AnyMessage], add_messages]
    conversation_stage: ConversationStage
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


def _initialize_components():
    try:
        prompt = ChatPromptTemplate.from_messages(
            [
                ("system", prompt_template.get("SYSTEMPROMPT", "")),
                ("placeholder", "{messages}"),
            ]
        )

        stack_prompt = PromptTemplate.from_template(
            load_yaml_file(Path(STACK_PROMPT_PATH)).get("STACKPROMPT", "")
        )

        stack_generator = stack_prompt | model

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
            return state
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
            # print("Converstaion Stage: ", self.conversation_stage)
            state = self._initialize_state(state)
            messages = state["messages"]
            # conversation_state = state["conversation_stage"]
            print("Converstaion state: ", state["conversation_stage"])
            print("Interaction Count: ", state["user_interaction_count"])
            state["user_interaction_count"] += 1

            # print("Messages: ", messages)
            last_user_message = next(
                (m for m in reversed(messages) if isinstance(m, HumanMessage)), None
            )

            # Track conversation progress
            if last_user_message:
                state["last_user_response"] = last_user_message.content
                user_msg = last_user_message.content.lower()
                # print("Last User Message: ", user_msg)

                if any(greet in user_msg for greet in ["hi", "hello", "hey"]):
                    state["conversation_stage"] = ConversationStage.greeting
                    return self._push(
                        state,
                        "👋 Hello! I'm your AI Solution Architect. I specialize in designing optimal technology stacks.\n\n"
                        "Let's start with your project goal...",
                    )

                # Update conversation stage based on user input
                elif state["conversation_stage"] == ConversationStage.greeting:
                    state["conversation_stage"] = ConversationStage.specify_goal

                    return self._push(
                        state,
                        "Great! Let's begin with your project:\n\n"
                        "🧭 What are you building? (e.g., 'A patient management system', 'An educational platform')",
                    )

                elif state["conversation_stage"] == ConversationStage.specify_goal:
                    state["conversation_stage"] = ConversationStage.project_description

                    state["program_context"]["initiative"] = state["last_user_response"]
                    return self._push(state, "Briefly describe what you are building")

                elif (
                    state["conversation_stage"] == ConversationStage.project_description
                ):
                    state["conversation_stage"] = ConversationStage.domain

                    if not state["program_context"].get("initiative"):
                        state["program_context"]["initiative"] = state[
                            "last_user_response"
                        ]
                        return self._ask_for_domain(state)

                elif state["conversation_stage"] == ConversationStage.domain:
                    if not state["program_context"].get("domain"):
                        state["program_context"]["domain"] = state["last_user_response"]
                        state["conversation_stage"] = ConversationStage.pillar_questions
                        return self._start_pillar_questions(state)

                elif state["conversation_stage"] == ConversationStage.pillar_questions:
                    state = self._save_pillar_response(state)
                    return self._next_pillar_question(state)

                elif state["conversation_stage"] == ConversationStage.generate_summary:
                    state["conversation_stage"] == ConversationStage.recommend_stack
                    return await self._recommend_stack(state)

            # Initial greeting
            if state["conversation_stage"] == ConversationStage.greeting:
                state["conversation_stage"] = (
                    ConversationStage.awaiting_greeting_response
                )
                return self._push(
                    state,
                    "👋 Hello! I'm your AI Solution Architect. I specialize in designing optimal technology stacks.\n\n"
                    "Let's start with your project goal...",
                )

            # Handle empty state transitions
            if not state["program_context"].get("initiative"):
                return self._push(
                    state,
                    "🧭 What are you building? Describe your project in 1-2 sentences.\n"
                    "Examples:\n- 'A patient management system for clinics'\n"
                    "- 'An educational platform for K-12 students'",
                )

            if not state["program_context"].get("domain"):
                return self._ask_for_domain(state)

            # Continue with pillar questions
            return self._continue_converation(state)

        except Exception as e:
            logger.error(f"Error in run method: {e}")
            return self._push(
                state, "⚠️ Sorry, I encountered an error. Let me try again..."
            )

    def _ask_for_domain(self, state: State) -> Dict:
        common_domains = self.domain_manager.knowledge["common_domains"]
        return self._push(
            state,
            "🌍 What industry/domain does this serve?\n"
            f"Common domains: {', '.join(common_domains)}\n"
            "Or specify your own:",
        )

    def _get_pillar_questions(self, state: State) -> Dict:
        cur_pillar = state["current_pillar"]
        pillar_responses = state["pillar_responses"].get(cur_pillar, {})
        pillar_questions = self.questions[cur_pillar]
        print(pillar_responses)
        for question in pillar_questions:
            if question not in pillar_responses.keys():
                return state, question

        # Check pillar is not in completed pillars
        if cur_pillar not in state["completed_pillars"]:
            state["completed_pillars"].append(cur_pillar)

        return state, None

    def _start_pillar_questions(self, state: State) -> Dict:
        state["current_pillar"] = self._get_next_pillar(state)
        if state["current_pillar"]:
            state, question = self._get_pillar_questions(state)

            if question == None:
                raise "Something is wrong"

            return self._push(
                state,
                f"📋 Now let's discuss {state['current_pillar'].replace('_', ' ').title()} requirements... \n {question}",
            )
        return self._generate_summary(state)

    def _next_pillar_question(self, state: State) -> Dict:
        print(state["pillar_responses"])
        if state["current_pillar"]:
            state, question = self._get_pillar_questions(state)

            # If there are no more question for that pillar
            if question == None:
                return self._start_pillar_questions(state)

            return self._push(state, f"{question}")
        return self._generate_summary(state)

    def _save_pillar_response(self, state: State) -> Dict:
        question = self._get_pillar_questions(state)[1]
        cur_pillar = state["current_pillar"]
        # print(question)
        if cur_pillar:
            pillar_repsonses = state["pillar_responses"].get(cur_pillar, {})
            pillar_repsonses[question] = state["last_user_response"]
            state["pillar_responses"][cur_pillar] = pillar_repsonses
            return state
        else:
            raise "Error"

    def _get_next_pillar(self, state: State) -> Optional[str]:
        for pillar in self.questions.keys():
            if pillar not in state["completed_pillars"]:
                return pillar
        return None

    def _generate_summary(self, state: State) -> Dict:
        state["conversation_stage"] = ConversationStage.generate_summary
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

    def _continue_converation(self, state: State) -> Dict:
        return {"messages": [self.runnable.invoke(state["messages"])]}


# === Graph Setup ===
assistant = Assistant(
    runnable=components["assistant_runnable"], questions=components["pillar_questions"]
)


async def assistant_node(state: State, config: RunnableConfig) -> Dict:
    # print(config)
    # print(state)
    return await assistant.run(state, config)


def techstack_agent_graph(memory):
    builder = StateGraph(State)
    builder.add_node("assistant", assistant_node)
    builder.add_node("tools", ToolNode(components["tools_to_use"]))
    builder.add_edge(START, "assistant")
    builder.add_conditional_edges("assistant", tools_condition)
    builder.add_edge("tools", "assistant")
    return builder.compile(memory)


memory = MemorySaver()

agent = techstack_agent_graph(memory)

agent.update_state
# Comment save image part
# file_path = 'output_image.png'
# output = agent.get_graph().draw_mermaid_png()

# # Write the PNG data to the file
# with open(file_path, 'wb') as f:
#     f.write(output)

# print(f"Image saved as {file_path}")

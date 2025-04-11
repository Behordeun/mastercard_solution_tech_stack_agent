from langchain_openai import ChatOpenAI
from langchain_groq import ChatGroq

from src.mastercard_solution_tech_stack_agent.config.appconfig import env_config

if env_config.llm == "GROQ":
    agent_model = ChatGroq(
        model="llama-3.1-8b-instant",
        temperature=0,
        max_tokens=None,
        timeout=None,
        max_retries=2,
        api_key=env_config.groq_api_key
    )   
else:
    agent_model = ChatOpenAI(
        model="gpt-4o-mini",
        temperature=0.4,
        max_tokens=None,
        timeout=None,
        max_retries=2,
        api_key=env_config.openai_api_key,
    )

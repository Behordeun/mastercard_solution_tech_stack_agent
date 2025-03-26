from langchain_openai import ChatOpenAI

from src.config.appconfig import env_config

model = ChatOpenAI(
    model="gpt-4o-mini",
    temperature=0.4,
    max_tokens=None,
    timeout=None,
    max_retries=2,
    api_key=env_config.openai_api_key,
)
agent_model = ChatOpenAI(
    model="gpt-4o-mini",
    temperature=0.4,
    max_tokens=None,
    timeout=None,
    max_retries=2,
    api_key=env_config.openai_api_key,
)

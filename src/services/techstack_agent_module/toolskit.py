# libraries
from typing import Annotated

from langchain_core.tools import tool

from src.config.db_setup import SessionLocal
from src.config.settings import Settings

settings = Settings()
db = SessionLocal()


@tool
def null(data: Annotated[str, ""]) -> str:
    pass

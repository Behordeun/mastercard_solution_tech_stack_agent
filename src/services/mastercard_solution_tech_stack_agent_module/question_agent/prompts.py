from langchain_core.output_parsers import JsonOutputParser
from src.utilities.helpers import load_pillar_questions
from langchain.prompts import load_prompt
from pydantic import BaseModel, Field
from typing import Optional

# Fetch all prompts
greeting_prompt = load_prompt("src/services/mastercard_solution_tech_stack_agent_module/prompts/greeting.yaml")
prompt_description_prompt = load_prompt("src/services/mastercard_solution_tech_stack_agent_module/prompts/project_description.yaml")
domain_prompt = load_prompt("src/services/mastercard_solution_tech_stack_agent_module/prompts/domain.yaml")
specify_goal_prompt = load_prompt("src/services/mastercard_solution_tech_stack_agent_module/prompts/specify_goal.yaml")

pillar_questions = load_pillar_questions("src/services/mastercard_solution_tech_stack_agent_module/data/Sample Pillars and Key Questions-Final copy.csv")


pillar_marker_prompt_template = load_prompt("src/services/mastercard_solution_tech_stack_agent_module/prompts/pillar_marker.yaml")

# Define your desired data structure.
class pillar_marker_formater(BaseModel):
    answer_ready: bool = Field(description="If the answer to the pillar question is well structured")
    answer: Optional[str] = Field(description="The provided answer")
    question: Optional[str] = Field(description="The new question")

pillar_marker_parser = JsonOutputParser(pydantic_object=pillar_marker_formater)

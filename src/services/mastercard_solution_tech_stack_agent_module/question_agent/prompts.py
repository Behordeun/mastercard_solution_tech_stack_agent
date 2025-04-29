from langchain.prompts import load_prompt
from src.utilities.helpers import load_pillar_questions

# Fetch all prompts
greeting_prompt = load_prompt("src/services/mastercard_solution_tech_stack_agent_module/prompts/greeting.yaml")
prompt_description_prompt = load_prompt("src/services/mastercard_solution_tech_stack_agent_module/prompts/project_description.yaml")
domain_prompt = load_prompt("src/services/mastercard_solution_tech_stack_agent_module/prompts/domain.yaml")
specify_goal_prompt = load_prompt("src/services/mastercard_solution_tech_stack_agent_module/prompts/specify_goal.yaml")


pillar_questions = load_pillar_questions("src/services/mastercard_solution_tech_stack_agent_module/data/Sample Pillars and Key Questions-Final copy.csv")


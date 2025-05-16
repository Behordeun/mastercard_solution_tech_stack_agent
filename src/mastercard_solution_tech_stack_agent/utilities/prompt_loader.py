import os

import yaml
from langchain_core.prompts import (ChatPromptTemplate,
                                    HumanMessagePromptTemplate)


def load_prompt_template_from_yaml(path: str) -> ChatPromptTemplate:
    with open(path, "r", encoding="utf-8") as file:
        yaml_data = yaml.safe_load(file)

    # Assume simple structure: one human message with template
    template = yaml_data.get("template", "")
    return ChatPromptTemplate.from_messages(
        [HumanMessagePromptTemplate.from_template(template)]
    )


def load_prompt(name: str) -> str:
    """Load a prompt from the YAML file by key."""
    prompts_path = os.path.join(
        os.path.dirname(__file__), "..", "prompts", f"{name}.yaml"
    )
    prompts_path = os.path.abspath(prompts_path)

    if not os.path.exists(prompts_path):
        raise FileNotFoundError(f"Prompt file not found: {prompts_path}")

    with open(prompts_path, "r", encoding="utf-8") as file:
        data = yaml.safe_load(file)
        if isinstance(data, dict) and "prompt" in data:
            return data["prompt"]
        elif isinstance(data, str):
            return data
        else:
            raise ValueError(f"Invalid YAML structure in {name}.yaml")

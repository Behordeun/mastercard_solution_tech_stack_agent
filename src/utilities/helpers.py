import re
from datetime import datetime as dts

import pandas as pd
import yaml


def load_yaml_file(file_path):
    """
    Reads a YAML file and returns its contents as a Python dictionary.
    """
    with open(file_path, "r") as file:
        data = yaml.safe_load(file)
    return data


def format_date(date_str: str) -> str | None:
    """Convert DD-MM-YYYY to YYYY-MM-DD format or return None for invalid dates."""
    if not date_str or date_str == "not provided" or date_str == "null":
        return None
    try:
        date_obj = dts.strptime(date_str, "%d-%m-%Y")
        return date_obj.strftime("%Y-%m-%d")
    except ValueError:
        return None


def get_day_date_month_year_time():
    """Returns current date & time components."""
    current_datetime = dts.now()
    return (
        current_datetime.strftime("%m-%d-%Y"),
        current_datetime.strftime("%A"),
        current_datetime.day,
        current_datetime.month,
        current_datetime.year,
        current_datetime.hour,
        current_datetime.minute,
        current_datetime.second,
    )


def check_final_answer_exist(string_to_check):
    """
    Check if 'final' and 'answer' exist in any form in the given string using regex.
    """
    pattern = re.compile(r"\bfinal[_\s]*answer\b|\banswer[_\s]*final\b", re.IGNORECASE)
    return bool(pattern.search(string_to_check))


# Static responses for recurrent sentences
static_responses = {
    "hello": "Hello! How can I assist you today?",
    "hi": "Hi there! How can I help you?",
    "are you online": "Yes, I am online and ready to assist you.",
    "are you there": "Yes, I am here. How can I assist you?",
    "good morning": "Good morning! How can I help you today?",
    "good afternoon": "Good afternoon! How can I assist you today?",
    "good evening": "Good evening! How can I help you today?",
}


async def static_response_generator(sentence):
    return sentence.lower()


def load_pillar_questions(csv_path: str) -> dict:
    """
    Loads pillar-based questions from a CSV and returns a dict: {pillar: [questions]}
    """
    df = pd.read_csv(csv_path)
    pillar_questions = {}
    for _, row in df.iterrows():
        pillar = row.get("Pillar")
        question = row.get("Key Question")

        if pd.isna(pillar) or pd.isna(question):
            continue  # Skip rows with missing data

        pillar = str(pillar).strip().lower()
        question = str(question).strip()

        if pillar and question:
            pillar_questions.setdefault(pillar, []).append(question)

    return pillar_questions

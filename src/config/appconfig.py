import os

from dotenv import load_dotenv

# ✅ Ensure .env is loaded
load_dotenv(override=True)


class EnvConfig:
    """Class to hold environment configuration variables."""

    def __init__(self):
        self.env = os.getenv("PYTHON_ENV")
        self.app_port = os.getenv("PORT")
        self.db_port = os.getenv("DB_PORT")
        self.auth_user = os.getenv("AUTH_USERNAME")
        self.auth_password = os.getenv("AUTH_PASSWORD")
        self.host = os.getenv("DB_HOST")
        self.database = os.getenv("DB_DATABASE")
        self.user = os.getenv("DB_USER")
        self.password = os.getenv("DB_PASSWORD")
        self.openai_api_key = os.getenv("OPENAI_API_KEY")

    def __repr__(self):
        return (
            f"EnvConfig(env={self.env}, app_port={self.app_port}, "
            f"auth_user={self.auth_user}, auth_password=****, "
            f"database={self.database}, user={self.user}, password=****)"
        )


# Create an instance of EnvConfig to access the environment variables
env_config = EnvConfig()

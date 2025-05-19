import os

from dotenv import load_dotenv

# ✅ Ensure .env is loaded
load_dotenv(override=True)


class EnvConfig:
    """Class to hold environment configuration variables."""

    def __init__(self):
        self.llm = os.getenv("LLM")
        self.env = os.getenv("PYTHON_ENV")
        self.app_port = os.getenv("PORT")
        self.db_port = os.getenv("DB_PORT")
        self.auth_user = os.getenv("AUTH_USERNAME")
        self.auth_password = os.getenv("AUTH_PASSWORD")
        self.host = os.getenv("DB_HOST")
        self.database = os.getenv("DB_DATABASE")
        self.database_url = os.getenv("POSTGRES_DB_URL")
        self.user = os.getenv("DB_USER")
        self.password = os.getenv("DB_PASSWORD")
        self.super_admin_email = os.getenv("SUPER_ADMIN_EMAIL")
        self.super_admin_password = os.getenv("SUPER_ADMIN_PASSWORD")
        self.admin_email = os.getenv("ADMIN_EMAIL")
        self.secret_key = os.getenv("SECRET_KEY")
        self.algorithm = os.getenv("ALGORITHM")
        self.token_type = os.getenv("TOKEN_TYPE")
        self.token_expire_minutes = int(os.getenv("TOKEN_EXPIRE_MINUTES", 30))
        self.openai_api_key = os.getenv("OPENAI_API_KEY")
        self.groq_api_key = os.getenv("GROQ_API_KEY")
        self.google_client_id = os.getenv("GOOGLE_CLIENT_ID")
        self.google_client_secret = os.getenv("GOOGLE_CLIENT_SECRET")
        self.google_redirect_uri = os.getenv("GOOGLE_REDIRECT_URI")
        self.google_auth_authorize_url = os.getenv("GOOGLE_AUTH_AUTHORIZE_URL")
        self.google_access_token_url = os.getenv("GOOGLE_AUTH_ACCESS_TOKEN_URL")

    def __repr__(self):
        return (
            f"EnvConfig(env={self.env}, app_port={self.app_port}, "
            f"auth_user={self.auth_user}, auth_password=****, "
            f"database={self.database}, user={self.user}, password=****)"
        )


# Create an instance of EnvConfig to access the environment variables
env_config = EnvConfig()

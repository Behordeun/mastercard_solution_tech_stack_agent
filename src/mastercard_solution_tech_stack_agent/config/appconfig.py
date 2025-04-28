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
        self.openai_api_key = os.getenv("OPENAI_API_KEY")
        self.groq_api_key = os.getenv("GROQ_API_KEY")
        self.email_port = os.getenv("EMAIL_PORT", 587)
        self.email_from = os.getenv("EMAIL_FROM")
        self.email_from_name = os.getenv("EMAIL_FROM_NAME")
        self.admin_email = os.getenv("ADMIN_EMAIL")
        self.mail_port = os.getenv("MAIL_PORT", 587)
        self.mail_username = os.getenv("MAIL_USERNAME", "apikey")
        self.mail_server = os.getenv("MAIL_SERVER", "smtp.sendgrid.net")
        self.mail_use_tls = os.getenv("MAIL_USE_TLS", True)
        self.mail_use_ssl = os.getenv("MAIL_USE_SSL", False)
        self.mail_ascii_attachments = os.getenv("MAIL_ASCII_ATTACHMENTS", True)
        self.use_credentials = os.getenv("USE_CREDENTIALS", True)
        self.validate_certs = os.getenv("VALIDATE_CERTS", True)
        self.sendgrid_api_key = os.getenv("SENDGRID_API_KEY")
        self.access_token_expire_minutes = os.getenv(
            "ACCESS_TOKEN_EXPIRE_MINUTES", 1440
        )
        self.algorithm = os.getenv("ALGORITHM", "HS256")
        self.secret_key = os.getenv("SECRET_KEY")
        self.super_admin_email = os.getenv("SUPER_ADMIN_EMAIL")
        self.server_base_address = os.getenv("SERVER_BASE_ADDRESS")
        self.google_client_id = os.getenv("GOOGLE_CLIENT_ID")
        self.google_client_secret = os.getenv("GOOGLE_CLIENT_SECRET")
        self.google_redirect_uri = os.getenv("GOOGLE_REDIRECT_URI")
        self.apple_client_id = os.getenv("APPLE_CLIENT_ID")
        self.apple_client_secret = os.getenv("APPLE_CLIENT_SECRET")
        self.cloudinary_api_key = os.getenv("CLOUDINARY_API_KEY")
        self.cloudinary_api_secret = os.getenv("CLOUDINARY_API_SECRET")
        self.cloudinary_url = os.getenv("CLOUDINARY_URL")
        self.cloudinary_cloud_name = os.getenv("CLOUDINARY_CLOUD_NAME")
        self.token_type = os.getenv("TOKEN_TYPE", "Bearer")
        self.server_base_address = os.getenv("SERVER_BASE_ADDRESS")
        self.google_auth_authorize_url = os.getenv(
            "GOOGLE_AUTH_AUTHORIZE_URL",
            "https://accounts.google.com/o/oauth2/auth",
        )
        self.google_auth_token_url = os.getenv(
            "GOOGLE_AUTH_TOKEN_URL",
            "https://oauth2.googleapis.com/token",
        )
        self.apple_auth_authorize_url = os.getenv(
            "APPLE_AUTH_AUTHORIZE_URL",
            "https://appleid.apple.com/auth/authorize",
        )
        self.apple_auth_access_token_url = os.getenv(
            "APPLE_AUTH_ACCESS_TOKEN_URL",
            "https://appleid.apple.com/auth/token",
        )

    def __repr__(self):
        return (
            f"EnvConfig(env={self.env}, app_port={self.app_port}, "
            f"auth_user={self.auth_user}, auth_password=****, "
            f"database={self.database}, user={self.user}, password=****)"
        )


# Create an instance of EnvConfig to access the environment variables
env_config = EnvConfig()

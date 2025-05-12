from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.mastercard_solution_tech_stack_agent.config.appconfig import env_config

REQUIRES_SSL = False

# Database setup
engine = create_engine(
    "postgresql+psycopg2://",
    connect_args={
        "user": env_config.user,
        "password": env_config.password,
        "host": env_config.host,
        "database": env_config.database,
    },
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

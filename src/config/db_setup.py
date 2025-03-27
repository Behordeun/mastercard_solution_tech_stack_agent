from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.config.appconfig import env_config

REQUIRES_SSL = False
DATABASE_URL = f"postgresql+asyncpg://{env_config.user}:{env_config.password}@{env_config.host}:{env_config.db_port}/{env_config.database}{'sslmode=require' if REQUIRES_SSL else ''}"

# Database setup
engine = create_engine(
    DATABASE_URL, 
    # "postgresql+psycopg2://",
    # connect_args={
    #     "user": env_config.user,
    #     "password": env_config.password,
    #     "host": env_config.host,
    #     "database": env_config.database,
    # },
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

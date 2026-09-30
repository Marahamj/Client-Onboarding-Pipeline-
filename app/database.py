import os 
from sqlalchemy import create_engine, text
from sqlalchemy.orm import declarative_base,sessionmaker
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+psycopg2://onboarding_user:onboarding_password@localhost:5432/onboarding_db",

)
engine = create_engine(DATABASE_URL)
SessionLocal= sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,

)

Base = declarative_base()
def get_db():
    db=SessionLocal()
    try:
        yield db
    finally:
        db.close()


def check_database_connection() -> bool:
    try:
        with engine.connect() as connection:
           connection.execute(text('SELECT 1'))
        return True
    except Exception:
        return False

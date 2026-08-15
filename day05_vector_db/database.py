from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv
import os

load_dotenv()

DATABASE_URL = os.environ.get("DATABASE_URL")
if not DATABASE_URL:
    raise RuntimeError ("DATABASE_URL not set, check .env is set and loade")


db_engine = create_engine(DATABASE_URL)

# Session factory - creates database sessions for queries/transactions
sessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=db_engine)


# Base class: all ORM models inherit from this
# Used by SQLAlchemy to define and track tables
Base = declarative_base()

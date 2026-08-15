import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))


from day05_vector_db.database import db_engine, Base
from day05_vector_db.models import Document
from sqlalchemy import text


with db_engine.connect() as conn:
    conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
    conn.commit()

Base.metadata.create_all(bind=db_engine)
print("Table recreated")
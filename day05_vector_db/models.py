from sqlalchemy import Column, Integer, String, DateTime, func, Index, UniqueConstraint
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects.postgresql import JSONB # JSONB, a PostgreSQL-specific data type for storing JSON data in a binary format, allowing for efficient storage and querying of JSON documents.

try:
    from .database import Base
except ImportError:  # pragma: no cover - allows running the module directly
    from database import Base


class Document(Base):

    __tablename__ = 'documents'

    id = Column(Integer, primary_key=True)
    content = Column(String)
    embedding = Column(Vector(1536))
    source = Column(String, nullable=False)
    chunk_index = Column(Integer, nullable=False)
    metadata_ = Column(JSONB) # 'metadata', JSONB is cause we want to store the metadata as a JSON object in the database, efficient querying of structured data.
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Adding an index on the embedding column using the HNSW algorithm to avoid full table scans (sequestial scan) during similarity search
    # which significantly improves query performance for large datasets as 
    # it enables Nearest Neighbor Search (NNS) on high-dimensional vector data.
    
    __table_args__ = (
        UniqueConstraint("source", "chunk_index", name="uq_source_chunk_index"),
        Index(
            "ix_documents_embedding_hnsw",
            "embedding",
            postgresql_using="hnsw",
            postgresql_with={"m": 16, "ef_construction": 64},
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
    )
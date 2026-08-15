"""
Day 5 Demo: Test VectorStore with Day 4's 50 sentences
Demonstrates:
1. Database setup and table creation
2. Upserting documents with embeddings
3. Vector similarity search
4. Metadata filtering
"""


# main.py is a test harness, nothing more. 
# It gets deleted (or becomes a tests/ file) once the FastAPI app is the caller.


from database import db_engine, sessionLocal, Base
from vector_store import VectorStore
from sqlalchemy import text
import pathlib


DATA_PATH = pathlib.Path(__file__).parent.parent / "data" / "sample.txt"  # Path to the sentences file


def setup_database():
    """Create tables and enable pgvector extension"""
    print("Setting up database...")
    
    # Enable pgvector extension
    with db_engine.connect() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        conn.commit()
    
    # Create all tables
    Base.metadata.create_all(bind=db_engine)
    print("Database setup complete\n")


def load_test_sentences():
    """Load 50 sentences from Day 4"""
    # You can replace this with reading from sentences.txt
    
    with open(DATA_PATH, "r") as f:
        sentences = [line.strip() for line in f if line.strip()]


    
    # Format as chunks for upsert
    """
    Update it to match the current models schema, since there have been some changes regarding the fields
    """
    chunks = [
        {
            "id": i + 1,
            "content": sentence,
            "metadata": {
                "source": "day4",
                "category": "tech" if i < 30 else "backend",
                "index": i
            }
        }
        for i, sentence in enumerate(sentences)
    ]
    
    return chunks


def test_upsert(vector_store, chunks):
    
    print("Testing upsert...")
    result = vector_store.upsert(chunks)
    
    if result["status"] == "success":
        print(f"Inserted {result['count']} documents\n")
    else:
        print(f"Error: {result['message']}\n")
    
    return result


def test_search(vector_store):
    """Test vector similarity search"""
    print("Testing similarity search...\n")
    
    queries = [
        "What is machine learning?",
        "Tell me about neural networks",
        "How does FastAPI work?",
        "What is a database?"
    ]
    
    for query in queries:
        print(f"Query: '{query}'")
        results = vector_store.search(query, top_k=3)
        
        if isinstance(results, dict) and results.get("status") == "error":
            print(f"Error: {results['message']}\n")
            continue
        
        for i, result in enumerate(results, 1):
            print(f"  {i}. [Score: {result['score']:.3f}] {result['content']}")
        print()


def test_filtered_search(vector_store):
    """Test search with metadata filtering"""
    print("Testing filtered search (category='backend')...\n")
    
    query = "What technologies do backend engineers use?"
    results = vector_store.search(query, top_k=5, filters={"category": "backend"})
    
    if isinstance(results, dict) and results.get("status") == "error":
        print(f"Error: {results['message']}\n")
        return
    
    print(f"Query: '{query}'")
    for i, result in enumerate(results, 1):
        print(f"  {i}. [Score: {result['score']:.3f}] {result['content']}")
        print(f"      Category: {result['metadata']['category']}")
    print()


def test_update(vector_store):
    """Test updating existing documents"""
    print("Testing document update...")
    
    updated_chunk = [{
        "id": 1,
        "content": "Machine learning is AI that learns from data without explicit programming.",
        "metadata": {"source": "day5_updated", "category": "tech", "index": 0}
    }]
    
    result = vector_store.upsert(updated_chunk)
    
    if result["status"] == "success":
        print(f"Updated document ID 1\n")
        
        # Verify update
        search_results = vector_store.search("What is machine learning?", top_k=1)
        print(f"Updated content: {search_results[0]['content']}")
        print(f"Metadata: {search_results[0]['metadata']}\n")
    else:
        print(f"Error: {result['message']}\n")


def test_delete(vector_store):
    """Test document deletion"""
    print("Testing deletion (source='day5_updated')...")
    
    result = vector_store.delete(filters={"source": "day5_updated"})
    
    if result["status"] == "success":
        print(f"Deleted {result['count']} documents\n")
    else:
        print(f"Error: {result['message']}\n")


def main():
    """Run all tests"""
    print("=" * 60)
    print("DAY 5: PGVECTOR VECTOR STORE TEST")
    print("=" * 60)
    print()
    
    # Setup
    setup_database()
    
    # Create session and vector store
    session = sessionLocal()
    vector_store = VectorStore(session)
    
    try:
        # Load test data
        chunks = load_test_sentences()
        
        # Run tests
        test_upsert(vector_store, chunks)
        test_search(vector_store)
        test_filtered_search(vector_store)
        test_update(vector_store)
        test_delete(vector_store)
        
        print("=" * 60)
        print("ALL TESTS COMPLETE")
        print("=" * 60)
        
    except Exception as e:
        import traceback
        traceback.print_exc()
    
    finally:
        session.close()


if __name__ == "__main__":
    main()

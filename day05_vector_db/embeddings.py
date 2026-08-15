from openai import OpenAI
import os
from dotenv import load_dotenv

load_dotenv()

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

def get_embeddings(docs):
    
    """
    Generate embeddings for a documents/list-of-documents using OpenAI's embedding model."""

    response = client.embeddings.create(
        input = docs,
        model = "text-embedding-3-small",
    )
    
    emebeddings = [item.embedding for item in response.data] # We extract only the embeddings from the respose

    return emebeddings # A list of vectors
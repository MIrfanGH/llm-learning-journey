import openai
import os
from dotenv import load_dotenv
import numpy as np

load_dotenv()


client = openai.OpenAI(api_key=os.environ.get('OPENAI_API_KEY'))


def load_sentences(): # To read sentences from the file and retun them as a list of strings.
    with open("day04_embeddings/sentences.txt", "r",  encoding="utf-8") as file:
        return [line.strip() for line in file if line.strip()]

sentences = load_sentences()


def get_embedding(query):
    response = client.embeddings.create(
        input = query,
        model = "text-embedding-3-small",   )
    return response.data[0].embedding # Returns the user query embedding.

def embedd_docs(sentences):
    response = client.embeddings.create(
        input = sentences,
        model = "text-embedding-3-small",   )
    
    embeddings =  [item.embedding for item in response.data] # Storing the embeddings in a list
    return embeddings


def cosine_similarity(vec_a, vec_b): 

    # Using numpy as it is optimized for vector operations and can handle large vectors efficiently.
    return np.dot(vec_a, vec_b) / (np.linalg.norm(vec_a) *np.linalg.norm(vec_b))


def search(query, doc_embeddings, sentences, top_k=5):
    query_embedding = get_embedding(query)
    scores = [cosine_similarity(query_embedding, doc_emb) for doc_emb in doc_embeddings]
    
    ranked = sorted(zip(sentences, scores), key=lambda x: x[1], reverse=True)
    
    return ranked[:top_k]


def main():
    
    # Step 1: Generate embeddings for all documents once
    doc_embeddings = embedd_docs(sentences)

    # Step 2: Get user query
    query = input("Enter your search query: ")

    # Step 3: Perform semantic search
    results = search(
        query=query,
        doc_embeddings=doc_embeddings,
        sentences=sentences,
        top_k=5
    )

    # Step 4: Display results
    print("\nTop 5 Most Similar Sentences:\n")
    for i, (sentence, score) in enumerate(results, start=1):
        print(f"{i}. Score: {score:.4f}")
        print(f"   {sentence}\n")


if __name__ == "__main__":
    main()
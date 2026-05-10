import sys, os   # To allow imports from sibling directories and to allow running script directly
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


from pydantic import BaseModel, ValidationError, Field
from typing import Literal
from openai import OpenAI
import os
import json
from dotenv import load_dotenv
from day02_classifier.day2_classifier import SYSTEM_PROMPT as SYSTEM_PROMPT02
load_dotenv()

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))



class QueryValidation(BaseModel):
  
    category: Literal["RAG", "TOOL", "GENERAL"] = Field(
        description= "Final query classification, must be one of the following: RAG, TOOL, GENERAL"
    )
    confidence: float = Field(
        ge = 0,
        le = 1,
        description= "Confidence score between 0.0 and 1.0 indicating how confident the model is in its classification"
    )
    reasoning: str = Field(
        min_length=10,
        max_length=200,

        description = "Short reason for classification."
    )
 

SYSTEM_PROMPT = SYSTEM_PROMPT02


def validation_and_retry(user_query: str, max_retries = 3) -> QueryValidation:

    messages = [
        { "role": "system", "content": SYSTEM_PROMPT},
        { "role": "user", "content": user_query},
    ]    

    for attempt in range(max_retries):
        # LLM call 
        response = client.chat.completions.create(
            model = "gpt-4o-mini",
            messages= messages,
            temperature=0.0,
        )

        raw = response.choices[0].message.content
        try:
            parsed = json.loads(raw)

            # Validation Check
            validated = QueryValidation.model_validate(parsed)
            return validated
        
        except json.JSONDecodeError as e:
                error_msg = f"Invalid JSON: {e}"
    
        except ValidationError as e:
                error_msg = f"Schema validation failed:\n{e}"

        # Retry Logic wuith feedback
        print(f"Attempt {attempt + 1} failed: {error_msg}")
        print("Retrying with feedback to the model...\n")

        messages.append({"role": "assistant", "content": raw})  # Providing the model with its previous output for context
        messages.append({"role": "user", "content": f"Your response had errors:\n{error_msg}\n\n. Please correct the output to match the required format and constraints."})


    raise ValueError(f"Failed after {max_retries} attempts. Last error: {error_msg}")
    
if __name__ == "__main__": 

    while True:
        query = input("qeury: ")

        if query.lower() == "quit":
            break
        if not query: # Handle empty input gracefully
             continue
        
        try:
            result = validation_and_retry(query)
            print(f"  → {result.category} (confidence: {result.confidence})")
            print(f"    Reasoning: {result.reasoning}\n")
        except ValueError as e:
            print(f"  → FAILED: {e}\n")

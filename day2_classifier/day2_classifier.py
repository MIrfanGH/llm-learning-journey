from openai import OpenAI
from dotenv import load_dotenv
import os
import json

load_dotenv()



"""
A Python script (day2_classifier.py) that:

- Takes any user message as input
- Sends it to an LLM with a well-crafted system prompt
- Returns strict JSON: {"category": "RAG" | "TOOL" | "GENERAL", "confidence": float, "reasoning": string}
- You test it with 30 varied inputs and log which ones failed (e.g. misclassified, low confidence, or no reasoning)
"""


client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))


def query_classifier(user_input : str):

    final_prompt = [{
    "role": "system",
    "content": """ You are a strict query classifier for an AI customer support agent

    TASK: Classify every user message into exactly one category.

    CATEGORIES: 
            - RAG: User is asking a question that can be answered from 
                    company documentation, FAQs, product info or knowledge base 
            - TOOL: User is requesting an action that requires calling 
                    an external system (cancel subscription, update email, 
                    send invoice, check order status)
            - GENERAL: Casual conversation, greetings, or questions not 
                    related to the product

    RULES: 
            - If a query could be RAG or TOOL, prefer TOOL (actions are 
            higher priority)
            - 
            - If unsure, classify as GENERAL
            - Never invent categories beyond RAG, TOOL, GENERAL
            - Confidence should be 0.0 to 1.0

    EXAMPLES:
            "What's your return policy?" → RAG (information lookup)
            "Cancel my order #1234" → TOOL (requires system action)
            "Hey there!" → GENERAL (greeting)
            "How do I change my password?" → RAG (how-to guide exists)
            "Change my password to xyz123" → TOOL (requires action)

    OUTPUT_FORMAT: 
            Always respond with this exact JSON, nothing else, no preamble, no markdown, no explanation outside the JSON:
            {"category": "RAG", "confidence": 0.85, "reasoning": "User asks about policy"} 
        

    CONSTRAINTS:
                - classify even if the user message is not in English
                - always classify into one of  "RAG" or "TOOL" or "GENERAL",  
                - Add no preamble, no markdown, no explanation outside the JSON."""
    }] 


    final_prompt.append({"role": "user", "content": user_input})
    response = client.chat.completions.create(
        model = "gpt-4o-mini",
        messages = final_prompt,
        temperature = 0, 
        # response_format = {"type": "json_object"},
    )

    reply = response.choices[0].message.content
    parsed_reply = json.loads(reply)
    return parsed_reply


if __name__ == "__main__":
    while True:
        user_input = input("Query: ")
        if user_input.lower() == "quit":
            break
        classification = query_classifier(user_input)
        print(f"Classification: {classification}\n")
        
    

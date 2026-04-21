import os
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()


client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

conversation_history = [
    {"role": "system",  "content": "You are a helpful asssistant. Keep response concise 2-3 sentenses max."}, 
    ]


def chat(user_input : str):

    conversation_history.append({"role": "user", "content": user_input})
    response = client.chat.completions.create(
        model="gpt-4o-mini", 
        messages= conversation_history,
        temperature=0, # 0 for deterministic response, 0.7 - 1 for more cretivity
        max_tokens=500, # Limit the response tokens, gpt 4o mini has 128k tokens limit, but we can set lower limit for response to save tokens and cost
    )

    reply = response.choices[0].message.content
    conversation_history.append({"role":"assistant","content":reply})

    usage = response.usage
    print(f"Tokens :  promtpt_tokens= {usage.prompt_tokens}, response= {usage.completion_tokens}, total= {usage.total_tokens},")

    return reply


if __name__ == "__main__":
    print("Chat started. Type 'quit' to exit.\n")

    while True:
        user_input = input("User: ")
        if user_input.lower() == "quit":
            break
        reply = chat(user_input)
        print(f"\nAssistant: {reply}\n")

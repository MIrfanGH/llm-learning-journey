import json
from pathlib import Path
import requests

RESPONSE_PATH = Path(__file__).parent / "evaluations_response.jsonl"
QUEATION_PATH = Path(__file__).parent / "eval_questions.json"

API_URL = "http://localhost:8000/ask"


def load_questions() -> list[dict]:
    with open(QUEATION_PATH, 'r') as f:
        questions = json.load(f)

    return questions # returns list of dicts containing eval data set



def run_single_query(question: str) -> dict: 
    try:
        load = {"query": question}
        r = requests.post(API_URL, json=load)

        r.raise_for_status() # # raises on 4xx/5xx, gets caught by your except below, avoids silent error entry in response file
        return r.json()
    except Exception as e:
        return {"error": str(e)}


def run_eval():

    questions = load_questions()

    with open(RESPONSE_PATH, 'w') as f:

        for q in questions:
            query = q['question']
            query_response = run_single_query(query)
            print(f"ran quetion: {q['id']}, successfully")
            res_row = {**q, "response": query_response}
            res = (json.dumps(res_row) + "\n") # prepares the data by taking the Python object and turning it into a JSON string. 
            f.write(res)  # writes that json string into the file
run_eval()
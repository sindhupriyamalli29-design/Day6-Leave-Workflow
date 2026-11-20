import time
import re
import os
import json
import csv
import requests
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()


# Step 1: Read the policy and split it into sections
def load_sections(policy_path="Day6_Leave_Policy.txt"):

    # Read the policy file
    policy = Path(policy_path).read_text(encoding="utf-8")

    # Find numbered sections and their contents
    pattern = r"(?ms)^(\d+)\.\s+([^\n]+)\n(.*?)(?=^\d+\.\s|\Z)"

    matches = re.findall(pattern, policy)

    sections = []

    # Store each section separately
    for number, title, content in matches:

        section = {
            "number": number,
            "title": title.strip(),
            "text": content.strip()
        }

        sections.append(section)

    return sections

# Step 2: Find the most relevant policy sections
def retrieve(question, sections, top_k=2):

    # Words that we don't need for matching
    skip_words = {
        "the", "and", "for", "can", "what", "how",
        "who", "does", "will", "when", "with", "are",
        "you", "your", "have", "any", "get", "much",
        "many", "there", "this", "that", "from", "after"
    }

    # Extract useful words from the question
    words = re.findall(r"[a-z]+", question.lower())

    words = [
        word for word in words
        if len(word) > 2 and word not in skip_words
    ]

    scored_sections = []

    # Compare question words with every policy section
    for section in sections:

        text = (
            section["title"] + " " + section["text"]
        ).lower()

        score = sum(
            1 for word in words
            if word[:5] in text
        )

        scored_sections.append({
            "section": section,
            "score": score
        })

    # Sort sections based on matching score
    scored_sections.sort(
        key=lambda item: item["score"],
        reverse=True
    )

    # Keep only sections with matching words
    best_matches = [
        item for item in scored_sections
        if item["score"] > 0
    ][:top_k]

    # No matching policy section
    if not best_matches:
        return {
            "question": question,
            "context": "NO MATCHING SECTION",
            "matches": []
        }

    # Prepare policy context for the AI
    context = "\n\n".join(
        f'{item["section"]["number"]}. '
        f'{item["section"]["title"]}\n'
        f'{item["section"]["text"]}'
        for item in best_matches
    )

    return {
        "question": question,
        "context": context,
        "matches": best_matches
    }

# Step 3: Test the retrieval system

    return {
        "question": question,
        "context": context,
        "matches": best_matches
    }



# Step 3: Ask the approved AI API to draft an answer
def get_draft(question, context):

    # If no policy section matches, do not call the AI
    if context == "NO MATCHING SECTION":
        return {
            "answer": "Not found in the leave policy",
            "source_section": None,
            "confidence": "low"
        }

    api_url = os.getenv("LLM_API_URL")
    api_key = os.getenv("LLM_API_KEY")
    model = os.getenv("LLM_MODEL")

    if not all([api_url, api_key, model]):
        raise ValueError(
            "Add the company-approved LLM API URL, key and model to .env"
        )

    prompt = f"""
You are a leave-policy assistant.
Answer using ONLY the policy context below.
Do not guess or add rules.

Return valid JSON with exactly these three keys:
answer, source_section, confidence.

source_section must be the section number as a string,
or null if the policy does not answer.
confidence must be high, medium, or low.
If the policy does not answer, use:
answer: Not found in the leave policy
source_section: null
confidence: low

Policy context:
{context}

Employee question:
{question}
"""

    response = requests.post(
        api_url,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        },
        json={
            "model": model,
            "messages": [
                {
                    "role": "system",
                    "content": "Return only valid JSON. Follow the requested keys exactly."
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            "temperature": 0
        },
        timeout=60
    )

        # Display the API error details if the request fails
    if response.status_code != 200:
        print("Gemini API error:", response.status_code)
        print("Details:", response.text)

    response.raise_for_status()

    raw_answer = response.json()["choices"][0]["message"]["content"]

    return parse_draft(raw_answer)    


# Step 4: Validate the AI's JSON response
def parse_draft(raw_answer):

    if isinstance(raw_answer, str):
        draft = json.loads(raw_answer)
    else:
        draft = raw_answer

    required_keys = {
        "answer",
        "source_section",
        "confidence"
    }

    if not isinstance(draft, dict) or set(draft.keys()) != required_keys:
        raise ValueError("AI response must contain exactly the three required keys.")

    if not isinstance(draft["answer"], str):
        raise ValueError("Answer must be text.")

    if draft["source_section"] is not None:
        draft["source_section"] = str(draft["source_section"])

    if draft["confidence"] not in ["high", "medium", "low"]:
        raise ValueError("Confidence must be high, medium or low.")

    return draft


# Step 5: Send data only after human approval
def send_to_mock_api(question, draft):

    webhook_url = os.getenv("WEBHOOK_URL")

    if not webhook_url:
        raise ValueError("Add your test webhook URL to .env first.")

    payload = {
        "question": question,
        "draft": draft,
        "status": "approved"
    }

    response = requests.post(
        webhook_url,
        json=payload,
        timeout=30
    )

    response.raise_for_status()

    return "Sent to mock API"


# Step 6: Run one question with human approval
def run_question(question):

    sections = load_sections()
    result = retrieve(question, sections)

    draft = get_draft(
        question,
        result["context"]
    )

    print("\nQuestion:", question)
    print("AI draft:")
    print(json.dumps(draft, indent=4))

    approval = input("\nApprove this answer? (y/n): ").strip().lower()

    if approval == "y":
        message = send_to_mock_api(question, draft)
        status = "Approved"
    else:
        message = "Rejected: nothing sent"
        status = "Rejected"

    print(message)

    return {
        "question": question,
        "answer": draft["answer"],
        "source_section": draft["source_section"],
        "confidence": draft["confidence"],
        "status": status,
        "action": message
    }


# Step 7: Run all five test questions and save a CSV log
def run_batch():

    questions = [
        "Can I carry over unused leave?",
        "Who approves my leave if my manager is on leave?",
        "Can I take half a day of sick leave?",
        "How many days in advance must I apply for casual leave?",
        "What's the canteen menu today?"
    ]

    results = []

    for question in questions:
        result = run_question(question)
        results.append(result)

    with open("test_log.csv", "w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(
            file,
            fieldnames=[
                "question",
                "answer",
                "source_section",
                "confidence",
                "status",
                "action"
            ]
        )

        writer.writeheader()
        writer.writerows(results)

    print("\nTest log saved as test_log.csv")


# Run the five-question workflow
if __name__ == "__main__":
    run_batch()


import json
import os
import re
import time
import requests

# Hardcoded configuration
SUBJECT_ID = "6570ae9f2bf08a793d969f64"
AUTH_TOKEN = "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpZCI6IjY4MzIwOGM3NzZhN2FiNTAxYjk0MGUzMSIsImlhdCI6MTc3OTUyMjQ2OSwiZXhwIjoxNzgyMTE0NDY5fQ.WYb5Fevk6IycFBEKh_W6L1CXZk09aeC2lhIqkufbdb8"
DELAY = 0.6

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:151.0) Gecko/20100101 Firefox/151.0",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Authorization": AUTH_TOKEN,
    "Sec-Fetch-Dest": "empty",
    "Sec-Fetch-Mode": "cors",
    "Sec-Fetch-Site": "same-origin",
}


def clean_name(name):
    """Removes invalid characters to make a safe directory or file name."""
    return re.sub(r'[\\/*?:"<>|]', "_", name).strip()


def make_request(url, params=None):
    """Helper to perform requests with the built-in delay."""
    time.sleep(DELAY)
    try:
        response = requests.get(url, headers=HEADERS, params=params)
        if response.status_code == 200:
            return response.json()
        else:
            print(f"\n[Error] HTTP {response.status_code} for URL: {url}")
            return None
    except Exception as e:
        print(f"\n[Exception] Failed to connect: {e}")
        return None


def fetch_chapters():
    """Fetches all chapters for the hardcoded subject ID."""
    url = f"https://web.getmarks.app/api/v1/lblq/subject/{SUBJECT_ID}"
    params = {"subjectClass": "", "sortBy": "", "limit": 100, "offset": 0}
    print("Fetching chapters list...")
    data = make_request(url, params)
    if data and data.get("success"):
        return data.get("data", {}).get("chapters", [])
    return []


def fetch_topics(chapter_id):
    """Fetches topics inside a specific chapter."""
    url = f"https://web.getmarks.app/api/v1/lblq/subject/{SUBJECT_ID}/chapter/{chapter_id}"
    params = {"tab": "topic", "limit": 100, "offset": 0, "show": "all"}
    data = make_request(url, params)
    if data and data.get("success"):
        return data.get("data", [])
    return []


def fetch_question_ids(chapter_id, topic_id):
    """Paginates and fetches all question objects (containing IDs) for a topic."""
    question_ids = []
    limit = 25
    offset = 0

    while True:
        url = f"https://web.getmarks.app/api/v1/lblq/subject/{SUBJECT_ID}/chapter/{chapter_id}/topic/{topic_id}"
        params = {"limit": limit, "offset": offset, "show": "all"}
        data = make_request(url, params)

        if not data or not data.get("success"):
            break

        topic_data = data.get("data", {})
        questions = topic_data.get("questions", [])
        for q in questions:
            if q.get("_id"):
                question_ids.append(q["_id"])

        total = data.get("total", 0)
        if len(question_ids) >= total or len(questions) == 0:
            break

        offset += limit

    return question_ids


def fetch_question_details(question_id):
    """Fetches specific question details and extracts only the essential fields."""
    url = f"https://web.getmarks.app/api/v1/questions/{question_id}"
    data = make_request(url)

    if not data or not data.get("success"):
        return None

    q_data = data.get("data", {})

    # Strip down options to keep only ID and Text, and find the correct option ID
    cleaned_options = []
    correct_option_id = None
    for opt in q_data.get("options", []):
        cleaned_options.append({"id": opt.get("id"), "text": opt.get("text")})
        if opt.get("isCorrect") is True:
            correct_option_id = opt.get("id")

    # Keep only the requested fields
    return {
        "question": q_data.get("question", {}).get("text"),
        "options": cleaned_options,
        "correct_option_id": correct_option_id,
        "solution": q_data.get("solution", {}).get("text"),
    }


def main():
    # 1. Base Directory
    base_dir = os.path.join("data", "Chemistry")
    os.makedirs(base_dir, exist_ok=True)

    # 2. Get Chapters
    chapters = fetch_chapters()
    if not chapters:
        print("No chapters found. Please check your AUTH_TOKEN.")
        return

    print(f"Found {len(chapters)} chapters. Processing...")

    # 3. Iterate Chapters
    for chap_idx, chap in enumerate(chapters, start=1):
        chap_details = chap.get("chapterId", {})
        chap_id = chap_details.get("_id")
        raw_chap_title = chap_details.get("title", f"Chapter_{chap_idx}")

        if not chap_id:
            continue

        chap_title_clean = clean_name(raw_chap_title)
        chap_dir = os.path.join(base_dir, chap_title_clean)
        os.makedirs(chap_dir, exist_ok=True)

        print(
            f"\n--- [{chap_idx}/{len(chapters)}] Chapter: {chap_title_clean} ---"
        )

        # 4. Get Topics inside Chapter
        topics = fetch_topics(chap_id)
        print(f"Found {len(topics)} topics in this chapter.")

        for topic_idx, topic in enumerate(topics, start=1):
            topic_id = topic.get("_id")
            raw_topic_title = topic.get("title", f"Topic_{topic_idx}")

            if not topic_id:
                continue

            topic_title_clean = clean_name(raw_topic_title)
            file_path = os.path.join(chap_dir, f"{topic_title_clean}.json")

            # Skip if this topic has already been successfully scraped in a previous run
            if os.path.exists(file_path):
                print(f"  [{topic_idx}/{len(topics)}] Skipping (Already Scraped): {topic_title_clean}")
                continue

            print(f"  [{topic_idx}/{len(topics)}] Topic: {topic_title_clean}")

            # 5. Get all Question IDs for this topic
            question_ids = fetch_question_ids(chap_id, topic_id)
            print(f"    Found {len(question_ids)} questions to fetch.")

            topic_questions = []

            # 6. Fetch details for each question ID
            for q_idx, q_id in enumerate(question_ids, start=1):
                print(
                    f"    Fetching question details {q_idx}/{len(question_ids)}...",
                    end="\r",
                )
                q_details = fetch_question_details(q_id)
                if q_details:
                    topic_questions.append(q_details)

            # 7. Save Topic JSON inside the Chapter Folder
            if topic_questions:
                with open(file_path, "w", encoding="utf-8") as f:
                    json.dump(topic_questions, f, indent=4, ensure_ascii=False)
                print(f"\n    Saved {len(topic_questions)} questions to {file_path}")
            else:
                print("\n    No questions retrieved for this topic.")


if __name__ == "__main__":
    main()

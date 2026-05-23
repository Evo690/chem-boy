import json
import os
import re
import time
import requests

# Hardcoded configurations
EXAM_ID = "615f0e999476412f48314daf"  # JEE Main
DELAY = 0.6

# Subject mapping
SUBJECTS = [
    {"id": "615f0c729476412f48314dab", "title": "Physics"},
    {"id": "615f0cf69476412f48314dac", "title": "Chemistry"},
    {"id": "615f0d109476412f48314dad", "title": "Mathematics"}
]

AUTH_TOKEN = "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpZCI6IjY4MzIwOGM3NzZhN2FiNTAxYjk0MGUzMSIsImlhdCI6MTc3OTUyMjQ2OSwiZXhwIjoxNzgyMTE0NDY5fQ.WYb5Fevk6IycFBEKh_W6L1CXZk09aeC2lhIqkufbdb8"

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


def fetch_chapters(subject_id):
    """Fetches all chapters for the given subject ID."""
    url = f"https://web.getmarks.app/api/v4/cpyqb/exam/{EXAM_ID}/subject/{subject_id}"
    params = {"platform": "web", "limit": 100, "offset": 0}
    print(f"Fetching chapters list for subject {subject_id}...")
    data = make_request(url, params)
    if data and data.get("success"):
        return data.get("chapters", {}).get("data", [])
    return []


def fetch_topics(subject_id, chapter_id):
    """Fetches topics inside a specific chapter."""
    url = f"https://web.getmarks.app/api/v4/cpyqb/exam/{EXAM_ID}/subject/{subject_id}/chapter/{chapter_id}/topics"
    params = {"syllabusCategory": "all"}
    data = make_request(url, params)
    if data and data.get("success"):
        return data.get("data", {}).get("topics", [])
    return []


def fetch_and_clean_questions(subject_id, chapter_id, topic_id):
    """Fetches and processes questions directly inside the loop (no extra detail endpoint needed)."""
    cleaned_questions = []
    limit = 25
    offset = 0

    while True:
        url = f"https://web.getmarks.app/api/v4/cpyqb/exam/{EXAM_ID}/subject/{subject_id}/chapter/{chapter_id}/topic/{topic_id}/questions"
        params = {
            "sortBy": "-previousYear",
            "hideOutOfSyllabus": "true",
            "limit": limit,
            "offset": offset,
        }

        data = make_request(url, params)
        if not data or not data.get("success"):
            break

        q_list = data.get("data", {}).get("questions", [])

        for q in q_list:
            q_type = q.get("type")
            q_text = q.get("question", {}).get("text")
            sol_text = q.get("solution", {}).get("text")

            cleaned_options = []
            correct_ans = None

            # 1. Handle Numerical type answers
            if q_type == "numerical":
                correct_ans = q.get("correctValue")
            # 2. Handle Multiple Choice answers
            else:
                for opt in q.get("options", []):
                    cleaned_options.append(
                        {"id": opt.get("id"), "text": opt.get("text")}
                    )
                    if opt.get("isCorrect") is True:
                        correct_ans = opt.get("id")

            cleaned_questions.append(
                {
                    "type": q_type,
                    "question": q_text,
                    "options": cleaned_options,
                    "correct_answer": correct_ans,
                    "solution": sol_text,
                }
            )

        total = data.get("data", {}).get("total", 0)
        if len(cleaned_questions) >= total or len(q_list) == 0:
            break

        offset += limit

    return cleaned_questions


def main():
    print(f"Starting Scraper for {len(SUBJECTS)} subjects...")

    for subject_entry in SUBJECTS:
        subject_id = subject_entry["id"]
        subject_title = subject_entry["title"]

        # 1. Subject Base Directory (e.g., data/Physics, data/Chemistry, data/Mathematics)
        base_dir = os.path.join("data", subject_title)
        os.makedirs(base_dir, exist_ok=True)

        print(f"\n==========================================")
        print(f"PROCESSING SUBJECT: {subject_title.upper()}")
        print(f"==========================================")

        # 2. Get Chapters
        chapters = fetch_chapters(subject_id)
        if not chapters:
            print(f"No chapters found for {subject_title}. Skipping.")
            continue

        print(f"Found {len(chapters)} chapters for {subject_title}.")

        # 3. Iterate Chapters
        for chap_idx, chap in enumerate(chapters, start=1):
            chap_id = chap.get("_id")
            raw_chap_title = chap.get("title", f"Chapter_{chap_idx}")

            if not chap_id:
                continue

            chap_title_clean = clean_name(raw_chap_title)
            chap_dir = os.path.join(base_dir, chap_title_clean)
            os.makedirs(chap_dir, exist_ok=True)

            print(
                f"\n--- [{subject_title}] [{chap_idx}/{len(chapters)}] Chapter: {chap_title_clean} ---"
            )

            # 4. Get Topics inside Chapter
            topics = fetch_topics(subject_id, chap_id)
            print(f"Found {len(topics)} topics in this chapter.")

            for topic_idx, topic in enumerate(topics, start=1):
                topic_id = topic.get("_id")
                raw_topic_title = topic.get("title", f"Topic_{topic_idx}")

                if not topic_id:
                    continue

                topic_title_clean = clean_name(raw_topic_title)
                file_path = os.path.join(chap_dir, f"{topic_title_clean}.json")

                # Skip if this topic has already been successfully scraped
                if os.path.exists(file_path):
                    print(
                        f"  [{topic_idx}/{len(topics)}] Skipping (Already Scraped): {topic_title_clean}"
                    )
                    continue

                print(f"  [{topic_idx}/{len(topics)}] Topic: {topic_title_clean}")

                # 5. Fetch and clean questions directly
                topic_questions = fetch_and_clean_questions(subject_id, chap_id, topic_id)

                # 6. Save Topic JSON inside the Chapter Folder
                if topic_questions:
                    with open(file_path, "w", encoding="utf-8") as f:
                        json.dump(topic_questions, f, indent=4, ensure_ascii=False)
                    print(f"    Saved {len(topic_questions)} questions to {file_path}")
                else:
                    print("    No questions retrieved for this topic.")


if __name__ == "__main__":
    main()

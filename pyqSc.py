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
        print(f"\n[Exception] Failed to connect/parse JSON: {e}")
        return None


def fetch_subjects():
    """Dynamically fetches active subjects for the exam."""
    url = f"https://web.getmarks.app/api/v4/cpyqb/exam/{EXAM_ID}"
    params = {"platform": "web"}
    print("Fetching subjects list dynamically...")
    
    data = make_request(url, params)
    
    if not data:
        print("  [Debug] Subject request failed completely.")
        return []
        
    if not data.get("success"):
        print(f"  [Debug] Subject API returned success=False. Response: {json.dumps(data)}")
        return []
        
    subjects_list = data.get("data", {}).get("subjects", [])
    
    cleaned_subjects = []
    for sub in subjects_list:
        sub_id = sub.get("_id")
        sub_title = sub.get("title")
        if sub_id and sub_title:
            cleaned_subjects.append({"id": sub_id, "title": sub_title})
            
    return cleaned_subjects


def fetch_chapters(subject_id):
    """Fetches all chapters for the given subject ID."""
    url = f"https://web.getmarks.app/api/v4/cpyqb/exam/{EXAM_ID}/subject/{subject_id}"
    
    # Matching the browser's parameters exactly
    params = {
        "platform": "web",
        "limit": 50,  # Requesting more than 25 to get all chapters in one go
        "offset": 0,
        "sortBy": "order",
        "syllabusCategory": "asPerSyllabus",
        "unit": "all",
        "subjectClass": "all"
    }
    print(f"Fetching chapters list for subject {subject_id}...")
    
    data = make_request(url, params)
    
    if not data:
        print(f"  [Debug] Chapter request failed completely.")
        return []
        
    if not data.get("success"):
        print(f"  [Debug] Chapter API returned success=False. Full response: {json.dumps(data)}")
        return []
        
    # Checking where 'chapters' is hiding
    root_chapters = data.get("chapters", {})
    inner_data_chapters = data.get("data", {}).get("chapters", {})
    
    # 1. Check if it's at the root (like your browser paste)
    if root_chapters:
        print("  [Debug] Found 'chapters' at root level.")
        return root_chapters.get("data", [])
        
    # 2. Check if it's nested inside 'data'
    elif inner_data_chapters:
        print("  [Debug] Found 'chapters' nested inside 'data'.")
        return inner_data_chapters.get("data", [])
        
    # 3. If missing in both, print keys to locate it
    else:
        print("  [Debug] 'chapters' key was missing from both root and inner 'data'.")
        print(f"  [Debug] Root Keys: {list(data.keys())}")
        print(f"  [Debug] Inner 'data' Keys: {list(data.get('data', {}).keys())}")
        if "message" in data:
            print(f"  [Debug] Message from server: {data['message']}")
            
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
    """Fetches and processes questions directly inside the loop."""
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

            if q_type == "numerical":
                correct_ans = q.get("correctValue")
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
    # 1. Fetch Subjects Dynamically
    subjects = fetch_subjects()
    if not subjects:
        print("Could not retrieve active subjects list. Stopping.")
        return

    print(f"Starting Scraper for {len(subjects)} dynamically fetched subjects...")

    for subject_entry in subjects:
        subject_id = subject_entry["id"]
        subject_title = subject_entry["title"]

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

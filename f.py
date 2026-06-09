import json
import os
import re
import time
import requests

# Hardcoded configurations
EXAMS = [
    {"id": "615f0e999476412f48314daf", "folder": "JEE_Main"},      # JEE Main
    {"id": "616059150283de43c87e3e21", "folder": "JEE_Advanced"}   # JEE Advanced
]
DELAY = 0.1

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
    """Removes invalid characters, newlines, and carriage returns to make a safe filename."""
    if not name:
        return name
    name = name.replace("\r", " ").replace("\n", " ").replace("\t", " ")
    name = re.sub(r'[\\/*?:"<>|]', "_", name)
    name = re.sub(r'\s+', ' ', name)
    return name.strip()


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


def download_chapter_icon(exam_folder, subject_title, icon_name):
    """Downloads the chapter-specific SVG icon using specific request headers."""
    if not icon_name:
        return
    
    save_dir = os.path.join("data", exam_folder, subject_title, "icons")
    os.makedirs(save_dir, exist_ok=True)
    file_path = os.path.join(save_dir, icon_name)

    # Skip if already downloaded
    if os.path.exists(file_path):
        return

    url = f"https://web.getmarks.app/icons/exam/{icon_name}"
    
    img_headers = {
        "User-Agent": HEADERS["User-Agent"],
        "Accept": "image/avif,image/webp,image/png,image/svg+xml,image/*;q=0.8,*/*;q=0.5",
        "Accept-Language": "en-US,en;q=0.9",
        "Referer": "https://web.getmarks.app/cpyqbV3/exam/615f0e999476412f48314daf",
        "Sec-Fetch-Dest": "image",
        "Sec-Fetch-Mode": "no-cors",
        "Sec-Fetch-Site": "same-origin",
        "Priority": "u=5, i",
        "TE": "trailers"
    }

    time.sleep(0.05)
    try:
        r = requests.get(url, headers=img_headers, stream=True, timeout=15)
        if r.status_code == 200:
            with open(file_path, "wb") as f:
                for chunk in r.iter_content(1024):
                    f.write(chunk)
            print(f"    Downloaded Chapter Icon: {icon_name}")
    except Exception as e:
        print(f"\n[Warning] Failed to download chapter icon {icon_name}: {e}")


def fetch_subjects(exam_id):
    """Dynamically fetches active subjects for the exam."""
    url = f"https://web.getmarks.app/api/v4/cpyqb/exam/{exam_id}"
    params = {"platform": "web"}
    print(f"Fetching subjects list dynamically for Exam ID: {exam_id}...")
    
    data = make_request(url, params)
    
    if not data:
        print("  [Debug] Subject request failed completely.")
        return []
        
    if not data.get("success"):
        print(f"  [Debug] Subject API returned success=False.")
        return []
        
    subjects_list = data.get("data", {}).get("subjects", [])
    
    cleaned_subjects = []
    for sub in subjects_list:
        sub_id = sub.get("_id")
        sub_title = sub.get("title")
        if sub_id and sub_title:
            cleaned_subjects.append({"id": sub_id, "title": sub_title})
            
    return cleaned_subjects


def fetch_chapters(exam_id, subject_id):
    """Fetches all chapters for the given subject ID."""
    url = f"https://web.getmarks.app/api/v4/cpyqb/exam/{exam_id}/subject/{subject_id}"
    params = {
        "platform": "web",
        "limit": 50,
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
        print(f"  [Debug] Chapter API returned success=False.")
        return []
        
    root_chapters = data.get("chapters", {})
    inner_data_chapters = data.get("data", {}).get("chapters", {})
    
    if root_chapters:
        return root_chapters.get("data", [])
    elif inner_data_chapters:
        return inner_data_chapters.get("data", [])
            
    return []


def fetch_topics(exam_id, subject_id, chapter_id):
    """Fetches topics inside a specific chapter."""
    url = f"https://web.getmarks.app/api/v4/cpyqb/exam/{exam_id}/subject/{subject_id}/chapter/{chapter_id}/topics"
    params = {"syllabusCategory": "all"}
    data = make_request(url, params)
    if data and data.get("success"):
        return data.get("data", {}).get("topics", [])
    return []


def fetch_and_clean_questions(exam_id, subject_id, chapter_id, topic_id):
    """Fetches questions and extracts all available properties (skips downloading images)."""
    cleaned_questions = []
    limit = 25
    offset = 0

    while True:
        url = f"https://web.getmarks.app/api/v4/cpyqb/exam/{exam_id}/subject/{subject_id}/chapter/{chapter_id}/topic/{topic_id}/questions"
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
            q_id = q.get("_id")
            q_type = q.get("type")
            q_difficulty = q.get("level")  # Difficulty (integer level)
            q_syllabus = q.get("syllabusCategory")  # Syllabus category (e.g. noChange)
            q_structure = q.get("questionStructure")  # Question layout structure

            # Get Year/Paper metadata
            year_obj = q.get("previousYear")
            if not year_obj and q.get("previousYearPapers"):
                year_obj = q.get("previousYearPapers")[0]
            
            q_year_title = year_obj.get("title") if year_obj else None
            q_year_short = year_obj.get("shortName") if year_obj else None
            q_held_on = year_obj.get("heldOn") if year_obj else None

            # Base question & solution content (keeping remote URLs)
            q_text = q.get("question", {}).get("text")
            q_img = q.get("question", {}).get("image")
            sol_text = q.get("solution", {}).get("text")
            sol_img = q.get("solution", {}).get("image")

            cleaned_options = []
            correct_ans = None

            if q_type == "numerical":
                correct_ans = q.get("correctValue")
            else:
                for opt in q.get("options", []):
                    cleaned_options.append(
                        {
                            "id": opt.get("id"), 
                            "text": opt.get("text"),
                            "image": opt.get("image")  # Keep original image URL
                        }
                    )
                    if opt.get("isCorrect") is True:
                        correct_ans = opt.get("id")

            cleaned_questions.append(
                {
                    "question_id": q_id,
                    "type": q_type,
                    "difficulty_level": q_difficulty,
                    "syllabus_category": q_syllabus,
                    "question_structure": q_structure,
                    "paper_year_title": q_year_title,
                    "paper_year_short": q_year_short,
                    "held_on": q_held_on,
                    "question_text": q_text,
                    "question_image": q_img,
                    "options": cleaned_options,
                    "correct_answer": correct_ans,
                    "solution_text": sol_text,
                    "solution_image": sol_img
                }
            )

        total = data.get("data", {}).get("total", 0)
        if len(cleaned_questions) >= total or len(q_list) == 0:
            break

        offset += limit

    return cleaned_questions


def generate_index():
    """Scans the physical data directory and builds index.json."""
    index = {}
    base_dir = "data"
    
    if not os.path.exists(base_dir):
        return

    # Loop exams (JEE_Main, JEE_Advanced)
    for exam in os.listdir(base_dir):
        exam_path = os.path.join(base_dir, exam)
        if not os.path.isdir(exam_path) or exam == "index.json":
            continue
        index[exam] = {}
        
        # Loop subjects (Physics, Chemistry, Mathematics)
        for subject in os.listdir(exam_path):
            sub_path = os.path.join(exam_path, subject)
            if not os.path.isdir(sub_path):
                continue
            index[exam][subject] = {}
            
            # Loop chapters
            for chapter in os.listdir(sub_path):
                chap_path = os.path.join(sub_path, chapter)
                if not os.path.isdir(chap_path) or chapter == "icons" or chapter == "images":
                    continue
                index[exam][subject][chapter] = []
                
                # Loop topics (.json files)
                for topic_file in os.listdir(chap_path):
                    if topic_file.endswith(".json"):
                        topic_name = topic_file[:-5]  # strip '.json'
                        index[exam][subject][chapter].append(topic_name)
                        
    index_path = os.path.join(base_dir, "index.json")
    with open(index_path, "w", encoding="utf-8") as f:
        json.dump(index, f, indent=4, ensure_ascii=False)
    print(f"\n[Index] Successfully generated browser index: {index_path}")


def main():
    print(f"Starting combined scraper for {len(EXAMS)} exams...")

    for exam_entry in EXAMS:
        exam_id = exam_entry["id"]
        exam_folder = exam_entry["folder"]

        # 1. Fetch Subjects Dynamically for current exam
        subjects = fetch_subjects(exam_id)
        if not subjects:
            print(f"Could not retrieve active subjects list for {exam_folder}. Skipping.")
            continue

        for subject_entry in subjects:
            subject_id = subject_entry["id"]
            subject_title = subject_entry["title"]

            # Subject Base Directory (e.g. data/JEE_Main/Physics)
            base_dir = os.path.join("data", exam_folder, subject_title)
            os.makedirs(base_dir, exist_ok=True)

            print(f"\n==========================================")
            print(f"PROCESSING: {exam_folder.upper()} -> {subject_title.upper()}")
            print(f"==========================================")

            # 2. Get Chapters
            chapters = fetch_chapters(exam_id, subject_id)
            if not chapters:
                print(f"No chapters found for {subject_title}. Skipping.")
                continue

            # 3. Iterate Chapters
            for chap_idx, chap in enumerate(chapters, start=1):
                chap_id = chap.get("_id")
                raw_chap_title = chap.get("title", f"Chapter_{chap_idx}")
                icon_name = chap.get("icon")

                if not chap_id:
                    continue

                chap_title_clean = clean_name(raw_chap_title)
                chap_dir = os.path.join(base_dir, chap_title_clean)
                os.makedirs(chap_dir, exist_ok=True)

                print(
                    f"\n--- [{exam_folder}] [{subject_title}] [{chap_idx}/{len(chapters)}] Chapter: {chap_title_clean} ---"
                )

                # Download the Chapter SVG Icon
                if icon_name:
                    download_chapter_icon(exam_folder, subject_title, icon_name)

                # 4. Get Topics inside Chapter
                topics = fetch_topics(exam_id, subject_id, chap_id)
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

                    # 5. Fetch and clean questions
                    topic_questions = fetch_and_clean_questions(exam_id, subject_id, chap_id, topic_id)

                    # 6. Save Topic JSON inside the Chapter Folder
                    if topic_questions:
                        with open(file_path, "w", encoding="utf-8") as f:
                            json.dump(topic_questions, f, indent=4, ensure_ascii=False)
                        print(f"    Saved {len(topic_questions)} questions to {file_path}")
                    else:
                        print("    No questions retrieved for this topic.")

    # Generate index.json representing the actual finished scrape
    generate_index()


if __name__ == "__main__":
    main()

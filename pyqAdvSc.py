import json
import os
import re
import time
import requests

# Hardcoded configurations for JEE Advanced
EXAM_ID = "616059150283de43c87e3e21"  
DELAY = 0.6

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


def download_image(url, save_dir):
    """Downloads an image file and returns its safe local filename."""
    os.makedirs(save_dir, exist_ok=True)
    
    # Extract filename from URL (remove query parameters)
    raw_filename = url.split("/")[-1].split("?")[0]
    filename = clean_name(raw_filename)
    file_path = os.path.join(save_dir, filename)

    if os.path.exists(file_path):
        return filename

    time.sleep(0.1)
    try:
        r = requests.get(url, headers={"User-Agent": HEADERS["User-Agent"]}, stream=True, timeout=15)
        if r.status_code == 200:
            with open(file_path, "wb") as f:
                for chunk in r.iter_content(1024):
                    f.write(chunk)
            return filename
    except Exception as e:
        print(f"\n[Warning] Failed to download image {url}: {e}")
    return None


def process_text_images(text, save_dir):
    """Finds image URLs in HTML tags, downloads them, and replaces URLs with relative paths."""
    if not text:
        return text

    urls = re.findall(r'src=["\'](https?://[^"\']+)["\']', text)

    for url in urls:
        # Check both getmarks and quizrr (which hosts JEE Advanced assets)
        if "getmarks.app" in url or "quizrr.in" in url:
            filename = download_image(url, save_dir)
            if filename:
                local_relative_path = f"../images/{filename}"
                text = text.replace(url, local_relative_path)
    return text


def process_direct_image(url, save_dir):
    """Downloads a standalone image URL and returns its relative path."""
    if not url:
        return None
    if "getmarks.app" in url or "quizrr.in" in url:
        filename = download_image(url, save_dir)
        if filename:
            return f"../images/{filename}"
    return url


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


def fetch_topics(subject_id, chapter_id):
    """Fetches topics inside a specific chapter."""
    url = f"https://web.getmarks.app/api/v4/cpyqb/exam/{EXAM_ID}/subject/{subject_id}/chapter/{chapter_id}/topics"
    params = {"syllabusCategory": "all"}
    data = make_request(url, params)
    if data and data.get("success"):
        return data.get("data", {}).get("topics", [])
    return []


def fetch_and_clean_questions(subject_id, subject_title, chapter_id, topic_id):
    """Fetches, cleans, downloads images, and extracts Year + Difficulty."""
    cleaned_questions = []
    limit = 25
    offset = 0
    
    images_dir = os.path.join("data", "JEE_Advanced", subject_title, "images")

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
            q_img = q.get("question", {}).get("image")
            sol_text = q.get("solution", {}).get("text")
            sol_img = q.get("solution", {}).get("image")

            # Extract Year Metadata
            year_obj = q.get("previousYear")
            if not year_obj and q.get("previousYearPapers"):
                year_obj = q.get("previousYearPapers")[0]
            
            q_year = year_obj.get("shortName") if year_obj else None
            q_difficulty = q.get("level")  # Extract Difficulty Level (integer)

            # Process Images
            q_text = process_text_images(q_text, images_dir)
            q_img = process_direct_image(q_img, images_dir)
            sol_text = process_text_images(sol_text, images_dir)
            sol_img = process_direct_image(sol_img, images_dir)

            cleaned_options = []
            correct_ans = None

            if q_type == "numerical":
                correct_ans = q.get("correctValue")
            else:
                for opt in q.get("options", []):
                    opt_text = opt.get("text")
                    opt_img = opt.get("image")

                    opt_text = process_text_images(opt_text, images_dir)
                    opt_img = process_direct_image(opt_img, images_dir)

                    cleaned_options.append(
                        {
                            "id": opt.get("id"), 
                            "text": opt_text,
                            "image": opt_img
                        }
                    )
                    if opt.get("isCorrect") is True:
                        correct_ans = opt.get("id")

            cleaned_questions.append(
                {
                    "type": q_type,
                    "difficulty": q_difficulty,
                    "year": q_year,
                    "question": q_text,
                    "image": q_img,
                    "options": cleaned_options,
                    "correct_answer": correct_ans,
                    "solution": sol_text,
                    "solution_image": sol_img
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

        # Subject Base Directory under JEE_Advanced folder
        base_dir = os.path.join("data", "JEE_Advanced", subject_title)
        os.makedirs(base_dir, exist_ok=True)

        print(f"\n==========================================")
        print(f"PROCESSING ADVANCED SUBJECT: {subject_title.upper()}")
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

                # 5. Fetch, clean, and download images
                topic_questions = fetch_and_clean_questions(subject_id, subject_title, chap_id, topic_id)

                # 6. Save Topic JSON inside the Chapter Folder
                if topic_questions:
                    with open(file_path, "w", encoding="utf-8") as f:
                        json.dump(topic_questions, f, indent=4, ensure_ascii=False)
                    print(f"    Saved {len(topic_questions)} questions to {file_path}")
                else:
                    print("    No questions retrieved for this topic.")


if __name__ == "__main__":
    main()

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


def download_chapter_icon(icon_name, save_dir):
    """Downloads the chapter-specific SVG icon using specific request headers."""
    if not icon_name:
        return
    os.makedirs(save_dir, exist_ok=True)
    file_path = os.path.join(save_dir, icon_name)

    # Skip if already downloaded
    if os.path.exists(file_path):
        return

    url = f"https://web.getmarks.app/icons/exam/{icon_name}"
    
    # Specific headers replicated from your curl call
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

    time.sleep(0.1)
    try:
        r = requests.get(url, headers=img_headers, stream=True, timeout=15)
        if r.status_code == 200:
            with open(file_path, "wb") as f:
                for chunk in r.iter_content(1024):
                    f.write(chunk)
            print(f"    Downloaded Chapter Icon: {icon_name}")
    except Exception as e:
        print(f"\n[Warning] Failed to download chapter icon {icon_name}: {e}")


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


def fetch_and_clean_questions(subject_id, chapter_id, topic_id):
    """Fetches questions and extracts all available properties (skips downloading images)."""
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
            q_year_short = year_obj.get("sho

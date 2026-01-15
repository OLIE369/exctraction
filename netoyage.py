import json
import re
from datetime import datetime, timedelta
from bs4 import BeautifulSoup
from rapidfuzz import process, fuzz

# --- Configuration ---
INPUT_FILE = 'last_results.json'
OUTPUT_FILE = 'cleaned_results.json'
DEFAULT_LOCATION = "Madagascar - National"

# Mappings for skill normalization
# Key: Canonical skill name
# Value: List of synonyms or variations to map to the key
SKILL_MAPPINGS = {
    "React": ["ReactJS", "React.js", "REACT", "react", "react use"],
    "Python": ["Python 3", "PYTHON", "python"],
    "Java": ["JAVA", "Java 8", "J2EE", "JEE"],
    "JavaScript": ["JS", "Javascript", "JAVASCRIPT", "EcmaScript"],
    "TypeScript": ["TS", "Typescript", "TYPESCRIPT"],
    "Node.js": ["Node", "NodeJS", "NODEJS", "node.js"],
    "SQL": ["sql", "Structured Query Language"],
    "NoSQL": ["nosql", "MongoDB", "CouchDB"], # Example of grouping
    "HTML/CSS": ["HTML", "CSS", "HTML5", "CSS3", "html", "css"],
    "PHP": ["php", "PHP 7", "PHP 8"],
    "Laravel": ["laravel", "LARAVEL"],
    "Symfony": ["symfony", "SYMFONY"],
    "Angular": ["AngularJS", "angular", "ANGULAR"],
    "Vue.js": ["Vue", "VueJS", "vue.js", "VUE"],
    "Docker": ["docker", "DOCKER"],
    "Kubernetes": ["k8s", "K8s", "kubernetes"],
    "AWS": ["Amazon Web Services", "aws"],
    "Azure": ["azure", "Microsoft Azure"],
    "Git": ["git", "GIT", "Github", "Gitlab"],
    "Linux": ["linux", "LINUX", "Ubuntu", "CentOS", "Debian"],
    "C#": ["c#", "C_Sharp", ".NET", "dotNET"],
    "C++": ["c++", "cpp"],
    "Go": ["Golang", "go", "GO"],
    "Rust": ["rust", "RUST"],
    "Excel": ["Microsoft Excel", "excel", "EXCEL", "Spreadsheets"],
    "Power BI": ["PowerBI", "power bi"],
}

# --- Functions ---

def clean_html(text):
    """
    Removes HTML tags and extra whitespace from text.
    """
    if not text:
        return ""
    
    # Use BeautifulSoup to remove HTML tags
    soup = BeautifulSoup(text, "html.parser")
    clean_text = soup.get_text(separator=" ")
    
    # Remove extra whitespace (multiple spaces, newlines, etc.)
    clean_text = re.sub(r'\s+', ' ', clean_text).strip()
    
    return clean_text

def normalize_skill(skill_name):
    """
    Normalizes a single skill name using strict mapping and fuzzy matching.
    """
    if not skill_name:
        return None

    # 1. Direct lookup in mappings (case-insensitive check could be added here if needed, but RapidFuzz handles similarity)
    # We flatten the mapping for easier lookup or just iterate.
    # For now, let's use RapidFuzz to find the best match amongst all known variations.
    
    all_variations = []
    for canonical, variations in SKILL_MAPPINGS.items():
        for v in variations:
            all_variations.append((v, canonical))
            
    # Simple check first
    for canonical, variations in SKILL_MAPPINGS.items():
        if skill_name == canonical or skill_name in variations:
            return canonical

    # Fuzzy matching
    # We want to match the input skill_name against our known variations.
    # If we find a high score match, we map it to the canonical name.
    
    choices = [v[0] for v in all_variations]
    match = process.extractOne(skill_name, choices, scorer=fuzz.WRatio)
    
    if match:
        best_match_str, score, index = match
        if score > 85: # Threshold for similarity
            # Find the canonical name for this variation
            for v_str, canonical in all_variations:
                if v_str == best_match_str:
                    return canonical
    
    # If no match found, return the original skill formatted (e.g., Title Case) or just as is
    return skill_name.strip() #.title() 

def normalize_skills_list(skills_detected):
    """
    Normalizes the structure of skills_detected from the scraper.
    """
    if not skills_detected:
        return {}

    normalized_skills = {}
    
    for category, skills in skills_detected.items():
        new_category_skills = []
        for skill in skills:
            norm_skill = normalize_skill(skill)
            if norm_skill and norm_skill not in new_category_skills:
                new_category_skills.append(norm_skill)
        
        if new_category_skills:
             normalized_skills[category] = new_category_skills
             
    return normalized_skills

def fill_missing_values(job):
    """
    Fills missing values with defaults.
    """
    if not job.get("location") or job["location"].strip() == "":
        job["location"] = DEFAULT_LOCATION
    
    # Add other missing value checks here if needed
    if not job.get("title"):
         job["title"] = "N/A"
         
    return job

def deduplicate_jobs(jobs):
    """
    Deduplicates jobs based on Title, Company, and Publication Date (within 24h).
    """
    unique_jobs = []
    seen_jobs = [] # List of tuples: (title, company, date_posted_obj)

    print(f"Initial job count: {len(jobs)}")

    for job in jobs:
        title = job.get("title", "").lower().strip()
        company = job.get("company", "").lower().strip()
        
        # Parse date
        date_str = job.get("date_posted", "")
        try:
            # Assuming date format from scraper: "2026-01-14 05:02:00"
            date_posted = datetime.strptime(date_str, "%Y-%m-%d %H:%M:%S")
        except ValueError:
            # Handle standard ISO format or other variations if necessary
            try:
                date_posted = datetime.fromisoformat(date_str)
            except:
                 # If date is invalid, we can't compare time, so strictly check title+company
                 # or treat as unique? Let's treat as current time for safety or skip time check
                 # For now, let's keep it if date is weird, but warn
                 # print(f"Warning: Could not parse date {date_str} for job {title}")
                 date_posted = datetime.min

        is_duplicate = False
        for seen_title, seen_company, seen_date in seen_jobs:
            if title == seen_title and company == seen_company:
                # Check time difference
                time_diff = abs(date_posted - seen_date)
                if time_diff < timedelta(hours=24):
                    is_duplicate = True
                    break
        
        if not is_duplicate:
            unique_jobs.append(job)
            seen_jobs.append((title, company, date_posted))
    
    print(f"Final job count: {len(unique_jobs)}")
    print(f"Removed {len(jobs) - len(unique_jobs)} duplicates.")
    return unique_jobs

# --- Main Execution ---

if __name__ == "__main__":
    try:
        print("Loading data...")
        with open(INPUT_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        cleaned_data = []
        print("Cleaning data...")
        for job in data:
            # 1. Clean HTML from description, missions, profile
            for field in ["description", "missions", "profile"]:
                if field in job:
                    job[field] = clean_html(job[field])
            
            # 2. Normalize Skills
            if "skills_detected" in job:
                job["skills_detected"] = normalize_skills_list(job["skills_detected"])
            
            # 3. Fill Missing Values
            job = fill_missing_values(job)
            
            cleaned_data.append(job)
            
        # 4. Deduplication
        print("Deduplicating...")
        final_data = deduplicate_jobs(cleaned_data)
        
        # Save output
        print(f"Saving to {OUTPUT_FILE}...")
        with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
            json.dump(final_data, f, ensure_ascii=False, indent=4)
            
        print("Data cleaning completed successfully.")

    except FileNotFoundError:
        print(f"Error: {INPUT_FILE} not found.")
    except Exception as e:
        print(f"An error occurred: {e}")
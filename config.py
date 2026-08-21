import os
from pathlib import Path
import yaml

# Try loading environment variables from .env file if python-dotenv is installed
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

BASE_DIR = Path(__file__).resolve().parent

# --- CONFIGURATION ---

# 1. Sheet Name
SHEET_NAME = os.getenv("SHEET_NAME", "Auto Job Scrapes")

# 2. Credentials File Path
cred_env = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
if cred_env and Path(cred_env).exists():
    CREDENTIALS_FILE = str(Path(cred_env).resolve())
else:
    # Auto-detect existing service account key files in root directory
    possible_keys = list(BASE_DIR.glob("linkedin-data-*.json")) + [
        BASE_DIR / "credentials.json",
        BASE_DIR / "service_account.json"
    ]
    existing_keys = [k for k in possible_keys if k.exists()]
    if existing_keys:
        CREDENTIALS_FILE = str(existing_keys[0])
    else:
        CREDENTIALS_FILE = str(BASE_DIR / "credentials.json")

# 3. Gemini API Key
GEMINI_APIKEY = os.getenv("GEMINI_API_KEY") or os.getenv("GEMINI_APIKEY")
if not GEMINI_APIKEY:
    # Legacy YAML fallback
    legacy_yaml = BASE_DIR / ".env/GEMINI_API_KEY.yaml"
    if legacy_yaml.exists():
        try:
            with open(legacy_yaml) as f:
                GEMINI_APIKEY = yaml.safe_load(f)
        except Exception as e:
            print(f"Warning: Failed to load legacy {legacy_yaml}: {e}")

# 4. OpenRouter API Key (Optional / Legacy)
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
if not OPENROUTER_API_KEY:
    legacy_openrouter_yaml = BASE_DIR / ".env/OPENROUTER_API_KEY.yaml"
    if legacy_openrouter_yaml.exists():
        try:
            with open(legacy_openrouter_yaml) as f:
                OPENROUTER_API_KEY = yaml.safe_load(f)
        except Exception as e:
            pass

# 5. Dynamic CV File Resolver
def get_cv_path() -> Path:
    """
    Dynamically locates candidate CV without requiring hardcoded filenames.
    Priority order:
    1. CV_PATH environment variable (if specified and file exists)
    2. Any .pdf, .docx, or .txt file inside the 'CVs/' directory
    3. Any .pdf, .docx, or .txt file inside the 'CVs_sample/' directory
    4. Default fallback: CVs_sample/sample_cv.txt
    """
    env_cv = os.getenv("CV_PATH")
    if env_cv and Path(env_cv).exists():
        return Path(env_cv).resolve()

    cvs_dir = BASE_DIR / "CVs"
    if cvs_dir.exists():
        valid_extensions = {".pdf", ".docx", ".txt"}
        cv_files = [
            f for f in cvs_dir.iterdir()
            if f.is_file() and f.suffix.lower() in valid_extensions and not f.name.startswith(".")
        ]
        if cv_files:
            # Sort to guarantee deterministic behavior
            cv_files.sort()
            return cv_files[0]

    sample_dir = BASE_DIR / "CVs_sample"
    if sample_dir.exists():
        sample_files = [
            f for f in sample_dir.iterdir()
            if f.is_file() and f.suffix.lower() in valid_extensions and not f.name.startswith(".")
        ]
        if sample_files:
            sample_files.sort()
            return sample_files[0]

    return sample_dir / "sample_cv.txt"

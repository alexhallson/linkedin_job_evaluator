import json
import asyncio
import time
from pathlib import Path
from google import genai
from google.genai import types
from config import GEMINI_APIKEY, BASE_DIR
from models import AIResponse

# Cache for the uploaded file object to avoid re-uploading on every request
# This persists as long as the uvicorn worker is alive.
CACHED_FILE_RESOURCE = None

class RateLimiter:
    def __init__(self, interval: float):
        self.interval = interval
        self.last_run = 0.0
        self.lock = asyncio.Lock()

    async def wait(self):
        async with self.lock:
            now = time.monotonic()
            elapsed = now - self.last_run
            wait_time = self.interval - elapsed
            if wait_time > 0:
                await asyncio.sleep(wait_time)
            self.last_run = time.monotonic()

GEMINI_LIMITER = RateLimiter(1.0)

async def get_ai_summary_from_pdf(job_description:str, cv_path: Path, job_title: str = "", job_location: str = ""):
    """
    Uploads a local PDF (or uses cached version) and calls Gemini for a concise summary
    forcing a structured JSON output using native schema enforcement.
    Uses async operations to avoid blocking the main event loop.
    Enforces a strict 1s rate limit between requests.
    """
    global CACHED_FILE_RESOURCE
    
    try:
        if not GEMINI_APIKEY:
            return "Error: GEMINI_APIKEY not found in config."

        # 1. Instantiate Client
        try:
            client = genai.Client(api_key=GEMINI_APIKEY)
        except Exception as e:
            return f"Error initializing Gemini client: {e}"

        # 2. Upload/Get File (Cached)
        if CACHED_FILE_RESOURCE is None:
            print("DEBUG: Uploading CV PDF to Gemini (First time)...")
            try:
                # Run blocking upload in a separate thread
                job_doc = await asyncio.to_thread(client.files.upload, file=cv_path)
                CACHED_FILE_RESOURCE = job_doc
                print(f"DEBUG: File uploaded successfully: {job_doc.name}")
            except Exception as e:
                return f"Error uploading file to Gemini: {e}"
        else:
            job_doc = CACHED_FILE_RESOURCE

        # 3. Prepare Prompt
        try:
            with open(BASE_DIR / "CV_prompt.txt") as f:
                prompt_content = f.read()
        except FileNotFoundError:
             return "Error: CV_prompt.txt not found."

        prompt = f"""
JOB DETAILS:
Title: {job_title}
Location: {job_location}

JOB DESCRIPTION:
{job_description}

INSTRUCTIONS:
{prompt_content}
"""

        # 4. Generate Content (Async Loop)
        for i in range(5):
            await GEMINI_LIMITER.wait()
            try:
                # blocking call wrapped in thread
                response = await asyncio.to_thread(
                    client.models.generate_content,
                    model='gemini-3.1-flash-lite', 
                    contents=[prompt, job_doc],
                    config={
                        "response_mime_type": "application/json",
                        "response_schema": AIResponse,
                    }
                )
                
                if response.text:
                    response_json = json.loads(response.text)
                    return response_json
                else:
                    return "Error: Empty response from AI."

            except Exception as e: 
                error_str = str(e)
                if "429" in error_str or "ResourceExhausted" in error_str:
                    print(f"Gemini Rate Limited (Attempt {i+1}/5).\nFull Error: {error_str}\nRetrying in 30s...")
                    await asyncio.sleep(30) # Explicit backoff for rate limit recovery
                # Handle Expired/Missing File
                elif "404" in error_str and "files/" in error_str:
                    print("DEBUG: Cached file seems lost/expired. Re-uploading...")
                    CACHED_FILE_RESOURCE = None
                    # We need to break context to re-upload, essentially recursing or just failing this attempt
                    # Simple fix: return error to force next job or handle re-upload logic better. 
                    # For now: invalidate cache and return error so user knows to retry?
                    # Or better: invalidate and allow next loop if possible? 
                    # The code structure makes re-uploading hard here without recursion.
                    # Let's return error and let the next call fix it.
                    return "Error: File resource expired. Please retry."
                elif "403" in error_str or "PermissionDenied" in error_str:
                    print("--- GEMINI API 403 FORBIDDEN ---")
                    return "Summary unavailable (403 Forbidden)."
                else:
                    print(f"Gemini API Error: {error_str}")
                    if i == 4: return f"Summary unavailable (Error: {error_str})"
                    
    except FileNotFoundError:
        return "Error: Local PDF file not found."
    except Exception as e:
        print(f"Unexpected Exception: {str(e)}")
        return f"Summary unavailable (Error: {str(e)})"

    return "Summary unavailable (API failed after retries)."

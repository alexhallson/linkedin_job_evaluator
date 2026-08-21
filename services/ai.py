import json
import os
import asyncio
import time
from pathlib import Path
from openai import AsyncOpenAI
from config import OPENAI_API_KEY, BASE_DIR
from models import AIResponse


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


OPENAI_LIMITER = RateLimiter(1.0)


def extract_cv_text(cv_path: Path) -> str:
    """
    Extract text from a local CV file (.pdf, .docx, or .txt).
    OpenAI chat completions do not accept raw PDFs, so we extract text locally.
    """
    suffix = cv_path.suffix.lower()
    if suffix == ".txt":
        return cv_path.read_text(encoding="utf-8", errors="ignore")

    if suffix == ".pdf":
        try:
            from pypdf import PdfReader
            reader = PdfReader(str(cv_path))
            parts = [page.extract_text() or "" for page in reader.pages]
            return "\n".join(parts)
        except Exception as e:
            raise RuntimeError(f"Failed to extract text from PDF: {e}")

    if suffix == ".docx":
        try:
            import docx
            document = docx.Document(str(cv_path))
            return "\n".join(p.text for p in document.paragraphs)
        except Exception as e:
            raise RuntimeError(f"Failed to extract text from DOCX: {e}")

    raise ValueError(f"Unsupported CV file type: {suffix}")


async def get_ai_summary_from_pdf(
    job_description: str,
    cv_path: Path,
    job_title: str = "",
    job_location: str = ""
):
    """
    Extracts text from a local CV and calls OpenAI for a structured evaluation
    of the candidate against the job description.

    Uses async operations to avoid blocking the event loop and enforces a
    strict 1s rate limit between requests.
    """
    try:
        if not OPENAI_API_KEY:
            return "Error: OPENAI_API_KEY not found in config."

        try:
            with open(BASE_DIR / "CV_prompt.txt") as f:
                prompt_content = f.read()
        except FileNotFoundError:
            return "Error: CV_prompt.txt not found."

        try:
            cv_text = extract_cv_text(cv_path)
        except Exception as e:
            return f"Error reading CV file: {e}"

        system_prompt = f"""You are an expert recruitment analyst.

Evaluate the candidate CV against the job details below according to the rubric.

JOB DETAILS:
Title: {job_title}
Location: {job_location}

JOB DESCRIPTION:
{job_description}

INSTRUCTIONS:
{prompt_content}

Respond ONLY with a valid JSON object matching the required schema.
"""

        client = AsyncOpenAI(api_key=OPENAI_API_KEY)
        model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

        for i in range(5):
            await OPENAI_LIMITER.wait()
            try:
                response = await client.chat.completions.create(
                    model=model,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": f"Candidate CV:\n\n{cv_text}"},
                    ],
                    response_format={"type": "json_object"},
                    temperature=0.2,
                )

                content = response.choices[0].message.content
                if not content:
                    return "Error: Empty response from AI."

                parsed = AIResponse(**json.loads(content))
                return parsed.model_dump()

            except Exception as e:
                error_str = str(e)
                if "rate limit" in error_str.lower() or "429" in error_str:
                    print(f"OpenAI rate limited (attempt {i+1}/5).\nFull error: {error_str}\nRetrying in 30s...")
                    await asyncio.sleep(30)
                elif "invalid_api_key" in error_str.lower() or "401" in error_str:
                    return "Summary unavailable (Invalid API key)."
                elif "insufficient_quota" in error_str.lower():
                    return "Summary unavailable (Quota exceeded)."
                else:
                    print(f"OpenAI API error: {error_str}")
                    if i == 4:
                        return f"Summary unavailable (Error: {error_str})"

    except Exception as e:
        print(f"Unexpected exception: {str(e)}")
        return f"Summary unavailable (Error: {str(e)})"

    return "Summary unavailable (API failed after retries)."

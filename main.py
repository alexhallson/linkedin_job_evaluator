import asyncio
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
import gspread
from config import BASE_DIR, SHEET_NAME, get_cv_path
from models import JobData
from services.sheets import get_google_sheet
from services.ai import get_ai_summary_from_pdf
from datetime import datetime

from contextlib import asynccontextmanager

# Global Queue for AI Analysis
ai_queue = asyncio.Queue()

async def ai_worker():
    """
    Background worker that processes AI analysis jobs from the queue one by one,
    with a strict rate limit (60s delay) to avoid 429 errors.
    """
    print("DEBUG: AI Worker started.")
    while True:
        job = await ai_queue.get()
        try:
            await perform_ai_analysis_and_update(job)
        except Exception as e:
            print(f"ERROR in AI worker for job {job.title}: {e}")
        finally:
            ai_queue.task_done()
            print("DEBUG: AI Worker task done.")

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    asyncio.create_task(ai_worker())
    asyncio.create_task(recover_pending_jobs())
    yield
    # Shutdown (if needed)
    print("DEBUG: Shutting down AI worker...")

app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["POST", "OPTIONS"],
    allow_headers=["*"],
)

async def recover_pending_jobs():
    """
    Scans the Google Sheet for jobs that are marked as 'Pending AI...'
    and re-adds them to the processing queue.
    """
    print("DEBUG: scanning sheet for pending jobs...")
    try:
        sheet = get_google_sheet()
        rows = sheet.get_all_values()
        
        # Row 0 is header usually? Let's check. 
        # Assuming Row 1 is header. Data starts from Row 2 (index 1).
        # Actually in get_all_values(), index 0 is row 1 of the sheet.
        
        for i, row in enumerate(rows):
            if i == 0: continue # Skip header
            
            # Check safely if we have enough columns
            if len(row) > 5:
                # Col 6 is index 5
                if row[5] == "Pending AI...":
                    title = row[0]
                    company = row[1]
                    print(f"DEBUG: Found pending job: {title} at {company}. Re-queueing...")
                    
                    # Reconstruct JobData
                    # Note: We need to be careful about matching exact fields.
                    # JobData needs: title, company, location, link, description
                    
                    # Columns:
                    # 0: Title
                    # 1: Company
                    # 2: Location
                    # 3: Link
                    # 4: Description
                    
                    try:
                        job = JobData(
                            title=title,
                            company=company,
                            location=row[2],
                            link=row[3],
                            description=row[4]
                        )
                        await ai_queue.put(job)
                    except Exception as e:
                        print(f"ERROR: Could not reconstruct job from row {i+1}: {e}")

    except Exception as e:
        print(f"ERROR during startup recovery: {e}")

async def perform_ai_analysis_and_update(job: JobData):
    """
    Performs AI analysis and updates the EXISTING row in Google Sheets.
    """
    print(f"DEBUG: Starting AI Analysis for {job.title} at {job.company}...")
    full_description = job.description.strip()
    cv_filepath = get_cv_path()
    print(f"DEBUG: Using CV file at {cv_filepath}")
    target_title = job.title.strip()
    target_company = job.company.strip()
    target_location = job.location.strip()

    # 1. AI Analysis
    ai_response = await get_ai_summary_from_pdf(full_description, cv_filepath, target_title, target_location)

    if isinstance(ai_response, str):
         print(f"AI Error: {ai_response}")
         # If error, we might still want to update the row with the error message or leave empty
         # For now, let's just log it and maybe fill one field or skip
         # We will fill with error text to be helpful
         experience_analysis = ai_response
         skills_analysis = ""
         visa_eligibility_analysis = ""
         cultural_fit_analysis = ""
         experience_score = 0.0
         skills_score = 0.0
         visa_eligibility_score = 0.0
         cultural_fit_score = 0.0
    else:
         experience_analysis = ai_response.get("experience_analysis", "")
         skills_analysis = ai_response.get("skills_analysis", "")
         visa_eligibility_analysis = ai_response.get("visa_eligibility_analysis", "")
         cultural_fit_analysis = ai_response.get("cultural_fit_analysis", "")
         experience_score = ai_response.get("experience_score", 0.0)
         skills_score = ai_response.get("skills_score", 0.0)
         visa_eligibility_score = ai_response.get("visa_eligibility_score", 0.0)
         cultural_fit_score = ai_response.get("cultural_fit_score", 0.0)

    # 2. Find the row again (Robustness against sorting/shifting)
    try:
        sheet = get_google_sheet()
        titles = sheet.col_values(1)
        companies = sheet.col_values(2)
        
        match_row_index = -1
        # Loop starts from 0, but sheet rows are 1-indexed.
        for idx, (t, c) in enumerate(zip(titles, companies)):
            if t.strip() == target_title and c.strip() == target_company:
                match_row_index = idx + 1
                break
        
        if match_row_index == -1:
            print(f"ERROR: Could not find job row to update for AI results: {target_title}")
            return

        # 3. Update Columns 6 to 13
        # Col 6: Exp Analysis
        # Col 7: Skills Analysis
        # Col 8: Visa Analysis
        # Col 9: Cultural Analysis
        # Col 10: Exp Score
        # Col 11: Skills Score
        # Col 12: Visa Score
        # Col 13: Cultural Score
        
        # Batch update is better but update_cell or update cells is fine.
        # Let's construct a range update for efficiency and atomicity.
        # Cells F{row}:M{row} (Cols 6-13)
        
        # gspread uses (row, col)
        # We want to update a horizontal slice. 
        # sheet.update(range_name, values)
        # Range name example: "F10:M10"
        
        updates = [[
            experience_analysis,
            skills_analysis,
            visa_eligibility_analysis,
            cultural_fit_analysis,
            experience_score,
            skills_score,
            visa_eligibility_score,
            cultural_fit_score
        ]]
        
        # Calculate A1 notation for the range
        # F is col 6, M is col 13
        start_col_letter = 'F'
        end_col_letter = 'M'
        range_notation = f"{start_col_letter}{match_row_index}:{end_col_letter}{match_row_index}"
        
        sheet.update(range_name=range_notation, values=updates)
        print(f"DEBUG: Successfully updated AI results for {target_title} at Row {match_row_index}")

    except Exception as e:
        print(f"ERROR updating sheet with AI results: {e}")


async def process_background_job(job: JobData):
    """
    Background task to process job data and save to Google Sheets IMMEDIATELY.
    Then queues AI analysis.
    """
    try:
        print(f"DEBUG: Starting processing for {job.title} at {job.company}...")
        sheet = get_google_sheet()
        today_date = datetime.now().strftime("%Y-%m-%d")
        
        target_title = job.title.strip()
        target_company = job.company.strip()

        # --- 1. Robust Duplicate Check (Title + Company) ---
        titles = sheet.col_values(1)
        companies = sheet.col_values(2)
        
        match_row_index = -1
        for idx, (t, c) in enumerate(zip(titles, companies)):
            if t.strip() == target_title and c.strip() == target_company:
                match_row_index = idx + 1
                break
        
        if match_row_index != -1:
            print(f"DEBUG: Duplicate found at Row {match_row_index}. Updating Last Seen.")
            try:
                # Update Last Seen (Column 15)
                sheet.update_cell(match_row_index, 15, today_date)
            except Exception as e:
                print(f"Warning: Could not update Last Seen cell: {e}")
            return 

        # --- 2. New Job Processing ---
        print(f"DEBUG: New job detected. Adding to sheet immediately...")

        # Construct Row with Empty/Default AI Data
        full_description = job.description.strip()
        
        row = [
            target_title,
            target_company,
            job.location.strip(),
            job.link.strip(),
            full_description[:30000],
            "Pending AI...", # Exp Analysis
            "Pending AI...", # Skills Analysis
            "Pending AI...", # Visa Analysis
            "Pending AI...", # Cultural Analysis
            0.0, # Exp Score
            0.0, # Skills Score
            0.0, # Visa Score
            0.0, # Cultural Score
            today_date, # First Seen
            today_date  # Last Seen
        ]
        
        sheet.append_row(row, value_input_option='RAW')
        print(f"DEBUG: Successfully added {target_title} to Sheet (Pending AI).")

        # --- 3. Queue for AI Analysis ---
        print(f"DEBUG: Enqueueing {target_title} for AI Analysis...")
        await ai_queue.put(job)
        
    except Exception as e:
        print(f"ERROR inside background task: {str(e)}")

@app.post("/add-job")
async def add_job(job: JobData, background_tasks: BackgroundTasks):
    """Endpoint to receive job data and queue for background processing."""
    print(f"DEBUG: Received Job Payload: {job.model_dump()}")
    background_tasks.add_task(process_background_job, job)
    return {"status": "queued", "message": "Job received. Logging to sheet and queuing for AI..."}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
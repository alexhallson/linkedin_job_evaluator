import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from fastapi.testclient import TestClient
from main import (
    app,
    process_background_job,
    recover_pending_jobs,
    perform_ai_analysis_and_update,
    ai_worker,
    JobData,
)

client = TestClient(app)

def test_add_job_endpoint():
    payload = {
        "title": "Backend Developer",
        "company": "Acme Corp",
        "location": "Remote",
        "link": "https://example.com/job/1",
        "description": "FastAPI developer needed."
    }
    with patch("main.process_background_job"):
        response = client.post("/add-job", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "queued"

@pytest.mark.asyncio
async def test_recover_pending_jobs():
    mock_sheet = MagicMock()
    mock_sheet.get_all_values.return_value = [
        ["Title", "Company", "Location", "Link", "Description", "Exp Analysis"], # Row 1 (Header)
        ["Dev", "Company A", "NY", "http://link1", "Desc 1", "Pending AI..."], # Pending
        ["Engineer", "Company B", "SF", "http://link2", "Desc 2", "Done"],       # Completed
    ]
    
    with patch("main.get_google_sheet", return_value=mock_sheet):
        with patch("main.ai_queue") as mock_queue:
            mock_queue.put = AsyncMock()
            await recover_pending_jobs()
            assert mock_queue.put.call_count == 1

@pytest.mark.asyncio
async def test_process_background_job_new():
    job = JobData(
        title="Python Dev",
        company="Tech Co",
        location="Remote",
        link="https://tech.co/job",
        description="Great role for Python devs"
    )
    
    mock_sheet = MagicMock()
    mock_sheet.col_values.side_effect = [
        ["Title"], # Existing titles
        ["Company"]  # Existing companies
    ]
    
    with patch("main.get_google_sheet", return_value=mock_sheet):
        with patch("main.ai_queue") as mock_queue:
            mock_queue.put = AsyncMock()
            await process_background_job(job)
            mock_sheet.append_row.assert_called_once()
            mock_queue.put.assert_called_once_with(job)


@pytest.mark.asyncio
async def test_process_background_job_duplicate():
    job = JobData(
        title="Python Dev",
        company="Tech Co",
        location="Remote",
        link="https://tech.co/job",
        description="Great role for Python devs"
    )
    
    mock_sheet = MagicMock()
    mock_sheet.col_values.side_effect = [
        ["Title", "Python Dev"],
        ["Company", "Tech Co"],
    ]
    
    with patch("main.get_google_sheet", return_value=mock_sheet):
        with patch("main.ai_queue") as mock_queue:
            mock_queue.put = AsyncMock()
            await process_background_job(job)
            mock_sheet.update_cell.assert_called_once()
            mock_queue.put.assert_not_called()


@pytest.mark.asyncio
async def test_process_background_job_error():
    job = JobData(
        title="Python Dev",
        company="Tech Co",
        location="Remote",
        link="https://tech.co/job",
        description="Great role for Python devs"
    )
    
    with patch("main.get_google_sheet", side_effect=Exception("sheets error")):
        with patch("main.ai_queue") as mock_queue:
            mock_queue.put = AsyncMock()
            await process_background_job(job)
            mock_queue.put.assert_not_called()


@pytest.mark.asyncio
async def test_recover_pending_jobs_skips_completed():
    mock_sheet = MagicMock()
    mock_sheet.get_all_values.return_value = [
        ["Title", "Company", "Location", "Link", "Description", "Exp Analysis"],
        ["Dev", "Company A", "NY", "http://link1", "Desc 1", "Done"],
    ]
    
    with patch("main.get_google_sheet", return_value=mock_sheet):
        with patch("main.ai_queue") as mock_queue:
            mock_queue.put = AsyncMock()
            await recover_pending_jobs()
            mock_queue.put.assert_not_called()


@pytest.mark.asyncio
async def test_recover_pending_jobs_reconstruct_error():
    mock_sheet = MagicMock()
    mock_sheet.get_all_values.return_value = [
        ["Title", "Company", "Location", "Link", "Description", "Exp Analysis"],
        ["Dev", "Company A", "NY", "http://link1", "Desc 1", "Pending AI..."],
    ]
    
    with patch("main.get_google_sheet", return_value=mock_sheet):
        with patch("main.ai_queue") as mock_queue:
            mock_queue.put = AsyncMock()
            with patch("main.JobData", side_effect=Exception("bad data")):
                await recover_pending_jobs()
                mock_queue.put.assert_not_called()


@pytest.mark.asyncio
async def test_perform_ai_analysis_updates_row():
    job = JobData(
        title="Python Dev",
        company="Tech Co",
        location="Remote",
        link="https://tech.co/job",
        description="Great role"
    )
    
    mock_response = {
        "experience_analysis": "Strong",
        "experience_score": 0.9,
        "skills_analysis": "Good",
        "skills_score": 0.8,
        "visa_eligibility_analysis": "Eligible",
        "visa_eligibility_score": 1.0,
        "cultural_fit_analysis": "Fit",
        "cultural_fit_score": 0.85,
    }
    
    mock_sheet = MagicMock()
    mock_sheet.col_values.side_effect = [
        ["Title", "Python Dev"],
        ["Company", "Tech Co"],
    ]
    
    with patch("main.get_google_sheet", return_value=mock_sheet):
        with patch("main.get_cv_path", return_value="/tmp/cv.pdf"):
            with patch("main.get_ai_summary_from_pdf", new=AsyncMock(return_value=mock_response)):
                await perform_ai_analysis_and_update(job)
                mock_sheet.update.assert_called_once()


@pytest.mark.asyncio
async def test_perform_ai_analysis_string_error_response():
    job = JobData(
        title="Python Dev",
        company="Tech Co",
        location="Remote",
        link="https://tech.co/job",
        description="Great role"
    )
    
    mock_sheet = MagicMock()
    mock_sheet.col_values.side_effect = [
        ["Title", "Python Dev"],
        ["Company", "Tech Co"],
    ]
    
    with patch("main.get_google_sheet", return_value=mock_sheet):
        with patch("main.get_cv_path", return_value="/tmp/cv.pdf"):
            with patch("main.get_ai_summary_from_pdf", new=AsyncMock(return_value="AI failed")):
                await perform_ai_analysis_and_update(job)
                mock_sheet.update.assert_called_once()


@pytest.mark.asyncio
async def test_perform_ai_analysis_row_not_found():
    job = JobData(
        title="Python Dev",
        company="Tech Co",
        location="Remote",
        link="https://tech.co/job",
        description="Great role"
    )
    
    mock_sheet = MagicMock()
    mock_sheet.col_values.side_effect = [
        ["Title", "Other Job"],
        ["Company", "Other Co"],
    ]
    
    with patch("main.get_google_sheet", return_value=mock_sheet):
        with patch("main.get_cv_path", return_value="/tmp/cv.pdf"):
            with patch("main.get_ai_summary_from_pdf", new=AsyncMock(return_value={})):
                await perform_ai_analysis_and_update(job)
                mock_sheet.update.assert_not_called()


@pytest.mark.asyncio
async def test_perform_ai_analysis_update_exception():
    job = JobData(
        title="Python Dev",
        company="Tech Co",
        location="Remote",
        link="https://tech.co/job",
        description="Great role"
    )
    
    mock_sheet = MagicMock()
    mock_sheet.col_values.side_effect = [
        ["Title", "Python Dev"],
        ["Company", "Tech Co"],
    ]
    mock_sheet.update.side_effect = Exception("update failed")
    
    with patch("main.get_google_sheet", return_value=mock_sheet):
        with patch("main.get_cv_path", return_value="/tmp/cv.pdf"):
            with patch("main.get_ai_summary_from_pdf", new=AsyncMock(return_value={})):
                await perform_ai_analysis_and_update(job)
                mock_sheet.update.assert_called_once()


@pytest.mark.asyncio
async def test_ai_worker_processes_job():
    job = JobData(
        title="Python Dev",
        company="Tech Co",
        location="Remote",
        link="https://tech.co/job",
        description="Great role"
    )
    
    mock_queue = MagicMock()
    mock_queue.get = AsyncMock(side_effect=[job, Exception("stop")])
    mock_queue.task_done = MagicMock()
    
    with patch("main.ai_queue", mock_queue):
        with patch("main.perform_ai_analysis_and_update", new=AsyncMock()) as mock_perform:
            with pytest.raises(Exception, match="stop"):
                await ai_worker()
            mock_perform.assert_called_once_with(job)
            mock_queue.task_done.assert_called_once()


@pytest.mark.asyncio
async def test_ai_worker_handles_job_error():
    job = JobData(
        title="Python Dev",
        company="Tech Co",
        location="Remote",
        link="https://tech.co/job",
        description="Great role"
    )
    
    mock_queue = MagicMock()
    mock_queue.get = AsyncMock(side_effect=[job, Exception("stop")])
    mock_queue.task_done = MagicMock()
    
    with patch("main.ai_queue", mock_queue):
        with patch("main.perform_ai_analysis_and_update", new=AsyncMock(side_effect=Exception("job failed"))) as mock_perform:
            with pytest.raises(Exception, match="stop"):
                await ai_worker()
            mock_perform.assert_called_once_with(job)
            mock_queue.task_done.assert_called_once()

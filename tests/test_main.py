import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from fastapi.testclient import TestClient
from main import app, process_background_job, recover_pending_jobs, JobData

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

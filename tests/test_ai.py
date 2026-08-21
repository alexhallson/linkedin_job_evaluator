import pytest
import asyncio
from unittest.mock import MagicMock, AsyncMock, patch
from pathlib import Path
from services.ai import RateLimiter, get_ai_summary_from_pdf

@pytest.mark.asyncio
async def test_rate_limiter():
    limiter = RateLimiter(0.1)
    start = asyncio.get_event_loop().time()
    await limiter.wait()
    await limiter.wait()
    elapsed = asyncio.get_event_loop().time() - start
    assert elapsed >= 0.1

@pytest.mark.asyncio
async def test_get_ai_summary_missing_apikey(monkeypatch):
    monkeypatch.setattr("services.ai.GEMINI_APIKEY", None)
    result = await get_ai_summary_from_pdf("JD text", Path("dummy.pdf"))
    assert "Error: GEMINI_APIKEY not found" in result

@pytest.mark.asyncio
async def test_get_ai_summary_missing_cv_prompt(tmp_path, monkeypatch):
    monkeypatch.setattr("services.ai.GEMINI_APIKEY", "fake-key")
    monkeypatch.setattr("services.ai.BASE_DIR", tmp_path) # prompt won't exist here
    
    mock_client = MagicMock()
    mock_client.files.upload.return_value = MagicMock(name="uploaded_file")
    
    with patch("services.ai.genai.Client", return_value=mock_client):
        result = await get_ai_summary_from_pdf("JD text", tmp_path / "dummy.pdf")
        assert "CV_prompt.txt not found" in result

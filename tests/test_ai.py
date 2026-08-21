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
    monkeypatch.setattr("services.ai.OPENAI_API_KEY", None)
    result = await get_ai_summary_from_pdf("JD text", Path("dummy.pdf"))
    assert "Error: OPENAI_API_KEY not found" in result


@pytest.mark.asyncio
async def test_get_ai_summary_missing_cv_prompt(tmp_path, monkeypatch):
    monkeypatch.setattr("services.ai.OPENAI_API_KEY", "fake-key")
    monkeypatch.setattr("services.ai.BASE_DIR", tmp_path)

    dummy_pdf = tmp_path / "dummy.pdf"
    dummy_pdf.write_text("dummy pdf content")

    with patch("services.ai.AsyncOpenAI") as mock_client_cls:
        result = await get_ai_summary_from_pdf("JD text", dummy_pdf)
        assert "CV_prompt.txt not found" in result
        mock_client_cls.assert_not_called()

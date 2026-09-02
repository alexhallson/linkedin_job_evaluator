import pytest
import asyncio
from unittest.mock import MagicMock, AsyncMock, patch
from pathlib import Path
from services.ai import RateLimiter, get_ai_summary_from_pdf
from models import AIResponse


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


@pytest.mark.asyncio
async def test_get_ai_summary_uses_structured_output(tmp_path, monkeypatch):
    monkeypatch.setattr("services.ai.OPENAI_API_KEY", "fake-key")
    monkeypatch.setattr("services.ai.BASE_DIR", tmp_path)

    prompt_file = tmp_path / "CV_prompt.txt"
    prompt_file.write_text("Evaluate the candidate.")

    cv_text = "Candidate has 10 years of Python experience."
    cv_file = tmp_path / "cv.txt"
    cv_file.write_text(cv_text)

    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message.content = (
        '{"experience_analysis": "Strong", "experience_score": 0.9, '
        '"skills_analysis": "Good", "skills_score": 0.8, '
        '"visa_eligibility_analysis": "Eligible", "visa_eligibility_score": 1.0, '
        '"cultural_fit_analysis": "Good fit", "cultural_fit_score": 0.85}'
    )

    mock_client = AsyncMock()
    mock_client.chat.completions.create = AsyncMock(return_value=mock_response)

    with patch("services.ai.AsyncOpenAI", return_value=mock_client):
        result = await get_ai_summary_from_pdf(
            "JD text", cv_file, job_title="Engineer", job_location="Remote"
        )

    assert isinstance(result, dict)
    assert result["experience_score"] == 0.9
    assert result["skills_score"] == 0.8

    call_kwargs = mock_client.chat.completions.create.call_args.kwargs
    assert call_kwargs["response_format"]["type"] == "json_schema"
    assert call_kwargs["response_format"]["json_schema"]["name"] == "AIResponse"
    assert call_kwargs["response_format"]["json_schema"]["strict"] is True
    assert "schema" in call_kwargs["response_format"]["json_schema"]
    assert call_kwargs["temperature"] == 0.1

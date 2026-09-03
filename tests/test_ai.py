import pytest
import asyncio
from unittest.mock import MagicMock, AsyncMock, patch
from pathlib import Path
from services.ai import RateLimiter, get_ai_summary_from_pdf, extract_cv_text
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
    assert call_kwargs["temperature"] == 1


def test_extract_cv_text_txt(tmp_path):
    cv_file = tmp_path / "cv.txt"
    cv_file.write_text("Plain text CV")
    assert extract_cv_text(cv_file) == "Plain text CV"


def test_extract_cv_text_pdf(tmp_path, monkeypatch):
    cv_file = tmp_path / "cv.pdf"
    cv_file.write_bytes(b"%PDF")

    mock_page = MagicMock()
    mock_page.extract_text.return_value = "PDF extracted text"
    mock_reader = MagicMock()
    mock_reader.pages = [mock_page]

    with patch("services.ai.PdfReader", return_value=mock_reader):
        result = extract_cv_text(cv_file)
        assert result == "PDF extracted text"


def test_extract_cv_text_pdf_failure(tmp_path):
    cv_file = tmp_path / "cv.pdf"
    cv_file.write_bytes(b"%PDF")

    with patch("services.ai.PdfReader", side_effect=Exception("pdf error")):
        with pytest.raises(RuntimeError, match="Failed to extract text from PDF"):
            extract_cv_text(cv_file)


def test_extract_cv_text_docx(tmp_path, monkeypatch):
    cv_file = tmp_path / "cv.docx"
    cv_file.write_bytes(b"docx")

    mock_para = MagicMock()
    mock_para.text = "DOCX paragraph"
    mock_doc = MagicMock()
    mock_doc.paragraphs = [mock_para]

    with patch("services.ai.docx.Document", return_value=mock_doc):
        result = extract_cv_text(cv_file)
        assert result == "DOCX paragraph"


def test_extract_cv_text_docx_failure(tmp_path):
    cv_file = tmp_path / "cv.docx"
    cv_file.write_bytes(b"docx")

    with patch("services.ai.docx.Document", side_effect=Exception("docx error")):
        with pytest.raises(RuntimeError, match="Failed to extract text from DOCX"):
            extract_cv_text(cv_file)


def test_extract_cv_text_unsupported(tmp_path):
    cv_file = tmp_path / "cv.xyz"
    cv_file.write_text("x")
    with pytest.raises(ValueError, match="Unsupported CV file type"):
        extract_cv_text(cv_file)


@pytest.mark.asyncio
async def test_get_ai_summary_rate_limit_retry(tmp_path, monkeypatch):
    monkeypatch.setattr("services.ai.OPENAI_API_KEY", "fake-key")
    monkeypatch.setattr("services.ai.BASE_DIR", tmp_path)

    prompt_file = tmp_path / "CV_prompt.txt"
    prompt_file.write_text("Evaluate the candidate.")

    cv_file = tmp_path / "cv.txt"
    cv_file.write_text("Candidate text")

    mock_client = AsyncMock()
    mock_client.chat.completions.create = AsyncMock(
        side_effect=Exception("rate limit 429")
    )

    mock_limiter = AsyncMock()
    monkeypatch.setattr("services.ai.OPENAI_LIMITER", mock_limiter)

    with patch("services.ai.AsyncOpenAI", return_value=mock_client):
        with patch("services.ai.asyncio.sleep", new=AsyncMock()) as mock_sleep:
            result = await get_ai_summary_from_pdf("JD", cv_file)
            assert "Summary unavailable" in result
            assert mock_sleep.call_count == 5


@pytest.mark.asyncio
async def test_get_ai_summary_invalid_api_key(tmp_path, monkeypatch):
    monkeypatch.setattr("services.ai.OPENAI_API_KEY", "fake-key")
    monkeypatch.setattr("services.ai.BASE_DIR", tmp_path)

    prompt_file = tmp_path / "CV_prompt.txt"
    prompt_file.write_text("Evaluate the candidate.")

    cv_file = tmp_path / "cv.txt"
    cv_file.write_text("Candidate text")

    mock_client = AsyncMock()
    mock_client.chat.completions.create = AsyncMock(
        side_effect=Exception("invalid_api_key 401")
    )

    with patch("services.ai.AsyncOpenAI", return_value=mock_client):
        result = await get_ai_summary_from_pdf("JD", cv_file)
        assert "Invalid API key" in result


@pytest.mark.asyncio
async def test_get_ai_summary_quota_exceeded(tmp_path, monkeypatch):
    monkeypatch.setattr("services.ai.OPENAI_API_KEY", "fake-key")
    monkeypatch.setattr("services.ai.BASE_DIR", tmp_path)

    prompt_file = tmp_path / "CV_prompt.txt"
    prompt_file.write_text("Evaluate the candidate.")

    cv_file = tmp_path / "cv.txt"
    cv_file.write_text("Candidate text")

    mock_client = AsyncMock()
    mock_client.chat.completions.create = AsyncMock(
        side_effect=Exception("insufficient_quota")
    )

    with patch("services.ai.AsyncOpenAI", return_value=mock_client):
        result = await get_ai_summary_from_pdf("JD", cv_file)
        assert "Quota exceeded" in result


@pytest.mark.asyncio
async def test_get_ai_summary_empty_response(tmp_path, monkeypatch):
    monkeypatch.setattr("services.ai.OPENAI_API_KEY", "fake-key")
    monkeypatch.setattr("services.ai.BASE_DIR", tmp_path)

    prompt_file = tmp_path / "CV_prompt.txt"
    prompt_file.write_text("Evaluate the candidate.")

    cv_file = tmp_path / "cv.txt"
    cv_file.write_text("Candidate text")

    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message.content = None

    mock_client = AsyncMock()
    mock_client.chat.completions.create = AsyncMock(return_value=mock_response)

    with patch("services.ai.AsyncOpenAI", return_value=mock_client):
        result = await get_ai_summary_from_pdf("JD", cv_file)
        assert "Empty response from AI" in result


@pytest.mark.asyncio
async def test_get_ai_summary_unexpected_exception(tmp_path, monkeypatch):
    monkeypatch.setattr("services.ai.OPENAI_API_KEY", "fake-key")
    monkeypatch.setattr("services.ai.BASE_DIR", tmp_path)

    prompt_file = tmp_path / "CV_prompt.txt"
    prompt_file.write_text("Evaluate the candidate.")

    cv_file = tmp_path / "cv.txt"
    cv_file.write_text("Candidate text")

    mock_client = AsyncMock()
    mock_client.chat.completions.create = AsyncMock(
        side_effect=Exception("unknown error")
    )

    with patch("services.ai.AsyncOpenAI", return_value=mock_client):
        result = await get_ai_summary_from_pdf("JD", cv_file)
        assert "Summary unavailable" in result
        assert "unknown error" in result

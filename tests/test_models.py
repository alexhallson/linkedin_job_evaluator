import pytest
from pydantic import ValidationError
from models import JobData, AIResponse

def test_job_data_valid():
    job = JobData(
        title="Software Engineer",
        company="TechCorp",
        location="Remote",
        description="Python FastAPI developer role",
        link="https://linkedin.com/jobs/view/123"
    )
    assert job.title == "Software Engineer"
    assert job.company == "TechCorp"
    assert job.location == "Remote"
    assert job.description == "Python FastAPI developer role"
    assert job.link == "https://linkedin.com/jobs/view/123"

def test_job_data_missing_field():
    with pytest.raises(ValidationError):
        JobData(
            title="Software Engineer",
            company="TechCorp"
            # Missing location, description, link
        )

def test_ai_response_valid():
    response = AIResponse(
        experience_analysis="Strong Python experience",
        experience_score=0.9,
        skills_analysis="FastAPI and Docker match well",
        skills_score=0.85,
        visa_eligibility_analysis="Local candidate, no sponsorship needed",
        visa_eligibility_score=1.0,
        cultural_fit_analysis="Startup experience matches company phase",
        cultural_fit_score=0.8
    )
    assert response.experience_score == 0.9
    assert response.skills_score == 0.85
    assert response.visa_eligibility_score == 1.0
    assert response.cultural_fit_score == 0.8

from typing import Optional

from pydantic import BaseModel, model_validator

class JobData(BaseModel):
    title: str
    company: str
    location: str
    description: str
    link: str

class AIResponse(BaseModel):
    experience_analysis: str
    experience_score: float
    skills_analysis: str
    skills_score: float
    visa_eligibility_analysis: str
    visa_eligibility_score: float
    cultural_fit_analysis: str
    cultural_fit_score: float
    internal_memo: Optional[dict] = None

    @model_validator(mode="before")
    @classmethod
    def flatten_internal_memo(cls, data):
        if isinstance(data, dict) and "internal_memo" in data:
            memo = data["internal_memo"]
            if isinstance(memo, dict):
                for key in (
                    "experience_analysis",
                    "experience_score",
                    "skills_analysis",
                    "skills_score",
                    "visa_eligibility_analysis",
                    "visa_eligibility_score",
                    "cultural_fit_analysis",
                    "cultural_fit_score",
                ):
                    if key not in data and key in memo:
                        data[key] = memo[key]
        return data

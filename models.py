from pydantic import BaseModel

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

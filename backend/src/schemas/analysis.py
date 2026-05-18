from pydantic import BaseModel

class AnalysisRequest(BaseModel):
    ad_id: str

class AnalysisResult(BaseModel):
    ad_id: str
    summary: str          # Claude explanation
    price_verdict: str    # 'rimligt', 'lågt', 'högt'
    risk_level: str       # 'låg', 'medel', 'hög'
    cached: bool          # whether this came from DB cache
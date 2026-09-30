from pydantic import BaseModel, Field

class DealWonRequest(BaseModel):
    crm_deal_id: str = Field(min_length=1)
    client_name: str =Field(min_length=1)
    client_email: str = Field(min_length=3)
    company_name: str = Field(min_length=1)
    service_type: str = Field(min_length=1)
    contract_value: int | None = Field(default=None,ge=0)
    currency: str | None = Field(default=None, max_length=10)
    project_brief: str | None = None
    assigned_team: list[str] = Field(default_factory=list)
class DealWonResponse(BaseModel):
     onboarding_id: int
     crm_deal_id : str
     status:str
     current_step: str | None
     

    
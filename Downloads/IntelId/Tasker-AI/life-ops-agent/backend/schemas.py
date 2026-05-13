from typing import List, Optional

from pydantic import BaseModel, Field


class SignupRequest(BaseModel):
    name: str = Field(..., min_length=2, max_length=120)
    email: str = Field(..., min_length=5, max_length=255)
    password: str = Field(..., min_length=8, max_length=128)


class LoginRequest(BaseModel):
    email: str = Field(..., min_length=5, max_length=255)
    password: str = Field(..., min_length=8, max_length=128)


class DecisionRequest(BaseModel):
    query: str = Field(..., min_length=3, max_length=500)
    debug: bool = False


class PreferencesUpdateRequest(BaseModel):
    budget_level: Optional[str] = Field(default=None, max_length=50)
    comfort_priority: Optional[str] = Field(default=None, max_length=50)
    health_sensitivity: Optional[str] = Field(default=None, max_length=50)
    preferred_modes: Optional[List[str]] = None
    home_location: Optional[str] = Field(default=None, max_length=200)
    work_location: Optional[str] = Field(default=None, max_length=200)
    notes: Optional[str] = Field(default=None, max_length=500)

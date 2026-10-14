from __future__ import annotations

from typing import Annotated, Any, Dict, List, Literal, Optional

from pydantic import BaseModel, EmailStr, Field, StringConstraints

from .core.config import settings

CityName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]
CityList = Annotated[List[CityName], Field(min_length=1, max_length=settings.MAX_CITIES_PER_REQUEST)]
Days = Annotated[int, Field(ge=1, le=settings.MAX_DAYS)]
Password = Annotated[str, StringConstraints(min_length=8, max_length=72)]  # bcrypt ignores > 72 bytes


# ---------- auth ----------
class SignupRequest(BaseModel):
    email: EmailStr
    password: Password


class LoginRequest(BaseModel):
    email: EmailStr
    password: Annotated[str, StringConstraints(min_length=1, max_length=72)]


class UserResponse(BaseModel):
    id: int
    email: str


# ---------- data ----------
class CityWindowIn(BaseModel):
    city: CityName
    days: Days = 7
    sources: Optional[List[str]] = None


class CompareIn(BaseModel):
    cities: CityList
    days: Days = 7


class ForecastIn(BaseModel):
    city: CityName
    horizonDays: Annotated[int, Field(ge=1, le=30)] = 7
    trainDays: Annotated[int, Field(ge=7, le=120)] = 30
    use_cache: bool = True


class ForecastMultiIn(BaseModel):
    cities: CityList
    horizonDays: Annotated[int, Field(ge=1, le=30)] = 7
    trainDays: Annotated[int, Field(ge=7, le=120)] = 30
    use_cache: bool = True


# ---------- agent ----------
class AgentPlanIn(BaseModel):
    prompt: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=1000)]


class ToolStep(BaseModel):
    name: str
    arguments: dict = Field(default_factory=dict)


class AgentPlanOut(BaseModel):
    plan: List[ToolStep]
    notes: Optional[str] = None
    irrelevant: bool = False
    reason: Optional[str] = None


class AgentExecIn(BaseModel):
    prompt: Optional[Annotated[str, StringConstraints(strip_whitespace=True, max_length=1000)]] = None
    plan: Optional[List[ToolStep]] = Field(default=None, max_length=10)


class AgentExecOut(BaseModel):
    answer: str
    trace: list
    final: Optional[dict] = None


# ---------- reports ----------
class ReportRequest(BaseModel):
    report_type: str
    payload: dict
    llm_notes: Optional[str] = None
    chart_images: Optional[List[str]] = None


class ReportIn(BaseModel):
    report_type: Literal["forecast", "comparison"]
    cities: List[str]
    metrics: Optional[Dict[str, Any]] = None
    stats: Optional[Dict[str, Any]] = None
    charts: Dict[str, str]
    options: Optional[Dict[str, Any]] = None

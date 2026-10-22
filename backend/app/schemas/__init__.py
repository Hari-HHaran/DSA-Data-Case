"""Pydantic request bodies. Responses are shaped by app/serializers.py."""
from datetime import date

from pydantic import BaseModel, Field


class LoginIn(BaseModel):
    username: str = Field(min_length=1, max_length=60)
    password: str = Field(min_length=1, max_length=200)


class DemoLoginIn(BaseModel):
    username: str = Field(min_length=1, max_length=60)


class RequestCreate(BaseModel):
    domain: str
    entity_code: str | None = None
    country_code: str | None = None
    department: str | None = ""
    request_type: str | None = "CREATE"
    priority: str | None = "NORMAL"
    data: dict[str, str | int | float | None] = Field(default_factory=dict)


class RequestUpdate(BaseModel):
    entity_code: str | None = None
    country_code: str | None = None
    department: str | None = None
    request_type: str | None = None
    priority: str | None = None
    data: dict[str, str | int | float | None] | None = None


class ValidateIn(BaseModel):
    domain: str
    entity_code: str | None = None
    country_code: str | None = None
    department: str | None = ""
    request_type: str | None = "CREATE"
    data: dict[str, str | int | float | None] = Field(default_factory=dict)
    attachments: list[str] = Field(default_factory=list)
    request_id: int | None = None


class DuplicateCheckIn(BaseModel):
    request_id: int | None = None
    domain: str | None = None
    country_code: str | None = None
    data: dict[str, str | int | float | None] | None = None


class DuplicateReviewIn(BaseModel):
    decision: str
    justification: str = ""
    candidate_id: int | None = None


class DecisionIn(BaseModel):
    comment: str = Field(default="", max_length=2000)


class VerifyIn(BaseModel):
    action: str = "VERIFY"
    comment: str = ""


class ManualResolveIn(BaseModel):
    sap_key: str = Field(min_length=1, max_length=40)
    comment: str = Field(min_length=5, max_length=1000)


class MappingReviewIn(BaseModel):
    decision: str  # CONFIRM | REJECT
    comment: str = ""


class OpportunityUpdate(BaseModel):
    status: str | None = None
    outcome: str | None = None
    note: str | None = None


class FollowupIn(BaseModel):
    assignee_id: int
    due_date: date | None = None
    note: str = Field(default="", max_length=2000)


class FieldIn(BaseModel):
    id: int | None = None
    key: str = Field(pattern=r"^[a-z][a-z0-9_]{1,59}$")
    label: str = Field(min_length=1, max_length=120)
    field_type: str = Field(pattern=r"^(text|textarea|email|phone|select|date|number)$")
    section: str = "Details"
    display_order: int = 0
    required: bool = False
    required_when: dict | None = None
    visible_when: dict | None = None
    options: list[str] | None = None
    pattern: str | None = None
    pattern_message: str | None = None
    help_text: str = ""
    sensitivity: str = Field(default="NONE", pattern=r"^(NONE|FINANCIAL)$")
    is_identifier: bool = False
    is_active: bool = True


class FormUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    fields: list[FieldIn]


class StepIn(BaseModel):
    id: int | None = None
    step_key: str = Field(pattern=r"^[a-z][a-z0-9_]{1,39}$")
    name: str = Field(min_length=1, max_length=120)
    role_code: str
    stage_order: int = Field(ge=1, le=20)
    condition: dict | None = None
    description: str = ""
    sla_days: int = Field(ge=1, le=30)
    is_active: bool = True


class WorkflowUpdate(BaseModel):
    name: str | None = None
    mdm_verification_sla_days: int | None = Field(default=None, ge=1, le=30)
    steps: list[StepIn]


class SettingUpdate(BaseModel):
    value: float | int | str | bool


class ImpactIn(BaseModel):
    assumptions: dict[str, float | None] = Field(default_factory=dict)

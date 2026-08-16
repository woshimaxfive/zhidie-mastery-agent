from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


SessionPhase = Literal["diagnostic", "guided_practice", "transfer_check", "completed"]
MasteryState = Literal["unassessed", "learning", "pending_verification", "mastered"]
EvidenceLevel = Literal["none", "assisted", "independent", "transfer_verified"]


class LearnerSummary(BaseModel):
    id: str
    display_name: str
    provider: str = "local"


class MasterySummary(BaseModel):
    knowledge_point_id: str
    knowledge_point_name: str
    mastery_state: MasteryState
    evidence_level: EvidenceLevel
    reason: str
    updated_at: str


class Recommendation(BaseModel):
    knowledge_point_id: str
    title: str
    reason: str
    action: Literal["start_session", "start_transfer_verification", "resume_session", "review_evidence"]
    session_id: str | None = None


class HomeResponse(BaseModel):
    learner: LearnerSummary
    recommendation: Recommendation
    mastery: MasterySummary


class TaskView(BaseModel):
    id: str
    kind: Literal["sequence_prediction", "parameter_construction"]
    prompt: str
    code: str | None = None
    target_sequence: list[int] | None = None
    answer_format: str


class HintView(BaseModel):
    level: int = Field(ge=1, le=3)
    content: str
    reveals_answer: bool = False


class AgentDecision(BaseModel):
    action: str
    title: str
    reason_codes: list[str]
    reason_summary: str
    mastery_effect: Literal["no_change", "pending_verification", "mastered"]
    next_step: str


class TraceSummary(BaseModel):
    trace_id: str
    tool: str
    label: str
    status: Literal["succeeded", "failed", "skipped"]
    started_at: str
    duration_ms: int


class SessionView(BaseModel):
    session_id: str
    revision: int
    session_phase: SessionPhase
    task: TaskView
    hint: HintView | None
    highest_hint_level: int = 0
    attempt_count: int = 0
    created_at: str
    updated_at: str


class SessionEnvelope(BaseModel):
    session: SessionView
    decision: AgentDecision
    mastery: MasterySummary
    trace: list[TraceSummary] = []


class CreateSessionRequest(BaseModel):
    knowledge_point_id: str = "python.range"


class AttemptRequest(BaseModel):
    task_id: str
    answer: str = Field(min_length=1, max_length=200)
    expected_revision: int = Field(ge=1)


class HintRequest(BaseModel):
    task_id: str
    expected_revision: int = Field(ge=1)


class AttemptView(BaseModel):
    id: str
    normalized_answer: list[int] | None
    correct: bool
    assistance_level: int
    diagnosis_code: str | None
    diagnosis: str


class AttemptResponse(BaseModel):
    attempt: AttemptView
    session: SessionView
    decision: AgentDecision
    mastery: MasterySummary
    trace: list[TraceSummary]


class EvidenceItem(BaseModel):
    evidence_id: str
    session_id: str
    task_id: str
    evidence_level: EvidenceLevel
    correct: bool
    hint_level: int
    summary: str
    created_at: str


class EvidenceResponse(BaseModel):
    mastery: MasterySummary
    required_next_evidence: str | None
    items: list[EvidenceItem]


class TraceItem(TraceSummary):
    input_summary: str
    output_summary: str
    error: str | None


class TraceResponse(BaseModel):
    session_id: str
    items: list[TraceItem]


class ApiErrorDetail(BaseModel):
    code: str
    message: str
    retryable: bool
    field: str | None = None
    request_id: str
    details: dict = {}


class ApiError(BaseModel):
    error: ApiErrorDetail

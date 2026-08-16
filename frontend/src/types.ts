export type SessionPhase = "diagnostic" | "guided_practice" | "transfer_check" | "completed";
export type MasteryState = "unassessed" | "learning" | "pending_verification" | "mastered";
export type EvidenceLevel = "none" | "assisted" | "independent" | "transfer_verified";

export interface MasterySummary {
  knowledge_point_id: string;
  knowledge_point_name: string;
  mastery_state: MasteryState;
  evidence_level: EvidenceLevel;
  reason: string;
  updated_at: string;
}

export interface AgentDecision {
  action: string;
  title: string;
  reason_codes: string[];
  reason_summary: string;
  mastery_effect: "no_change" | "pending_verification" | "mastered";
  next_step: string;
}

export interface TaskView {
  id: string;
  kind: "sequence_prediction" | "parameter_construction";
  prompt: string;
  code: string | null;
  target_sequence: number[] | null;
  answer_format: string;
}

export interface HintView {
  level: number;
  content: string;
  reveals_answer: boolean;
}

export interface TraceSummary {
  trace_id: string;
  tool: string;
  label: string;
  status: "succeeded" | "failed" | "skipped";
  started_at: string;
  duration_ms: number;
}

export interface TraceItem extends TraceSummary {
  input_summary: string;
  output_summary: string;
  error: string | null;
}

export interface SessionView {
  session_id: string;
  revision: number;
  session_phase: SessionPhase;
  task: TaskView;
  hint: HintView | null;
  hint_history: HintView[];
  highest_hint_level: number;
  attempt_count: number;
  created_at: string;
  updated_at: string;
}

export interface SessionEnvelope {
  session: SessionView;
  decision: AgentDecision;
  mastery: MasterySummary;
  trace: TraceSummary[];
}

export interface AttemptResponse extends SessionEnvelope {
  attempt: {
    id: string;
    normalized_answer: number[] | null;
    correct: boolean;
    assistance_level: number;
    diagnosis_code: string | null;
    diagnosis: string;
  };
}

export interface HomeResponse {
  learner: { id: string; display_name: string; provider: string };
  recommendation: {
    knowledge_point_id: string;
    title: string;
    reason: string;
    action: "start_session" | "start_transfer_verification" | "resume_session" | "review_evidence";
    session_id: string | null;
  };
  mastery: MasterySummary;
}

export interface EvidenceResponse {
  mastery: MasterySummary;
  required_next_evidence: string | null;
  items: Array<{
    evidence_id: string;
    session_id: string;
    task_id: string;
    evidence_level: EvidenceLevel;
    correct: boolean;
    hint_level: number;
    summary: string;
    created_at: string;
  }>;
}

export interface ApiErrorPayload {
  error: {
    code: string;
    message: string;
    retryable: boolean;
    field: string | null;
    request_id: string;
  };
}

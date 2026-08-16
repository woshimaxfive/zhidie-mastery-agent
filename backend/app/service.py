from __future__ import annotations

import json
import time
import uuid
from datetime import UTC, datetime

from fastapi import HTTPException

from .database import connect
from .rules import (
    DEFAULT_TRANSFER_VARIANT_ID,
    DIAGNOSTIC_EXPECTED,
    AnswerFormatError,
    diagnostic_hint,
    diagnose_diagnostic_answer,
    next_transfer_variant_id,
    parse_integer_list,
    parse_range_parameters,
    transfer_hint,
    transfer_variant,
)
from .schemas import (
    AgentDecision,
    AttemptResponse,
    AttemptView,
    EvidenceItem,
    EvidenceResponse,
    HintView,
    HomeResponse,
    LearnerSummary,
    MasterySummary,
    Recommendation,
    SessionEnvelope,
    SessionView,
    TaskView,
    TraceItem,
    TraceResponse,
    TraceSummary,
)


LEARNER_ID = "local-learner"
KNOWLEDGE_POINT_ID = "python.range"
KNOWLEDGE_POINT_NAME = "Python range()"


def now_iso() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


def api_error(status: int, code: str, message: str, *, field: str | None = None) -> HTTPException:
    return HTTPException(
        status_code=status,
        detail={
            "code": code,
            "message": message,
            "retryable": status >= 500 or code == "STALE_SESSION_REVISION",
            "field": field,
            "request_id": new_id("req"),
            "details": {},
        },
    )


def task_for_phase(phase: str, transfer_variant_id: str = DEFAULT_TRANSFER_VARIANT_ID) -> TaskView:
    if phase in {"diagnostic", "guided_practice"}:
        return TaskView(
            id="range-diagnostic-01",
            kind="sequence_prediction",
            prompt="写出这段代码生成的列表。",
            code="list(range(2, 10, 3))",
            answer_format="python_list",
        )
    variant = transfer_variant(transfer_variant_id)
    return TaskView(
        id=variant.id,
        kind="parameter_construction",
        prompt="构造一组 range() 参数，使它生成目标序列。",
        target_sequence=list(variant.target_sequence),
        answer_format="range_parameters",
    )


def mastery_from_row(row) -> MasterySummary:
    return MasterySummary(
        knowledge_point_id=KNOWLEDGE_POINT_ID,
        knowledge_point_name=KNOWLEDGE_POINT_NAME,
        mastery_state=row["mastery_state"],
        evidence_level=row["evidence_level"],
        reason=row["mastery_reason"],
        updated_at=row["updated_at"],
    )


def get_mastery_profile(connection):
    return connection.execute(
        """SELECT * FROM mastery_profiles
           WHERE learner_id = ? AND knowledge_point_id = ?""",
        (LEARNER_ID, KNOWLEDGE_POINT_ID),
    ).fetchone()


def save_mastery_profile(
    connection,
    mastery_state: str,
    evidence_level: str,
    mastery_reason: str,
    updated_at: str,
) -> None:
    connection.execute(
        """INSERT INTO mastery_profiles
           (learner_id, knowledge_point_id, mastery_state, evidence_level, mastery_reason, updated_at)
           VALUES (?, ?, ?, ?, ?, ?)
           ON CONFLICT (learner_id, knowledge_point_id) DO UPDATE SET
               mastery_state = excluded.mastery_state,
               evidence_level = excluded.evidence_level,
               mastery_reason = excluded.mastery_reason,
               updated_at = excluded.updated_at""",
        (
            LEARNER_ID,
            KNOWLEDGE_POINT_ID,
            mastery_state,
            evidence_level,
            mastery_reason,
            updated_at,
        ),
    )


def session_from_row(connection, row) -> SessionView:
    count = connection.execute(
        "SELECT COUNT(*) AS count FROM attempts WHERE session_id = ?", (row["id"],)
    ).fetchone()["count"]
    # 提示按等级累积：前端要展示 1..current 每一层，只给最后一层会让"渐进引导"无法被复查。
    variant = transfer_variant(row["transfer_variant_id"])

    def hint_at(level: int) -> str:
        if row["phase"] == "transfer_check":
            return transfer_hint(variant.target_sequence, level)
        return diagnostic_hint(row["last_diagnosis_code"], level)

    hint_history = [
        HintView(level=level, content=hint_at(level))
        for level in range(1, row["current_hint_level"] + 1)
    ]
    hint = hint_history[-1] if hint_history else None
    return SessionView(
        session_id=row["id"],
        revision=row["revision"],
        session_phase=row["phase"],
        task=task_for_phase(row["phase"], row["transfer_variant_id"]),
        hint=hint,
        hint_history=hint_history,
        highest_hint_level=row["highest_hint_level"],
        attempt_count=count,
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def decision_for_row(row) -> AgentDecision:
    if row["phase"] == "completed" and row["mastery_state"] == "mastered":
        return AgentDecision(
            action="review_evidence",
            title="迁移验证已经通过",
            reason_codes=["TRANSFER_VERIFIED"],
            reason_summary="你在当前迁移任务中没有使用提示，并生成了正确序列。",
            mastery_effect="mastered",
            next_step="查看掌握证据，或结束本次学习。",
        )
    if row["phase"] == "completed":
        return AgentDecision(
            action="retry_transfer_later",
            title="本次完成，仍需独立验证",
            reason_codes=["TRANSFER_ASSISTED"],
            reason_summary="迁移任务使用了提示，因此不能作为独立掌握证据。",
            mastery_effect="pending_verification",
            next_step="稍后在不使用提示的情况下重新完成迁移任务。",
        )
    if row["phase"] == "transfer_check":
        return AgentDecision(
            action="await_transfer",
            title="用新情境验证独立掌握",
            reason_codes=["TRANSFER_REQUIRED"],
            reason_summary="当前题目的正确结果还不足以证明可以迁移应用。",
            mastery_effect="no_change",
            next_step="构造参数并提交实际可执行的答案。",
        )
    if row["phase"] == "guided_practice":
        return AgentDecision(
            action="retry_or_request_hint",
            title="先修正当前理解",
            reason_codes=["DIAGNOSTIC_RETRY_REQUIRED"],
            reason_summary=row["mastery_reason"],
            mastery_effect="no_change",
            next_step="重新尝试，或在需要时请求下一层提示。",
        )
    return AgentDecision(
        action="await_answer",
        title="先独立完成诊断题",
        reason_codes=["INITIAL_DIAGNOSTIC"],
        reason_summary="还没有足够证据判断当前理解。",
        mastery_effect="no_change",
        next_step="提交你认为会生成的列表。",
    )


def record_trace(connection, session_id: str, tool: str, label: str, input_summary: str, output_summary: str,
                 *, status: str = "succeeded", error: str | None = None, duration_ms: int = 1) -> TraceSummary:
    trace_id = new_id("trace")
    started_at = now_iso()
    connection.execute(
        """INSERT INTO traces
           (id, session_id, tool, label, status, input_summary, output_summary, error, started_at, duration_ms)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (trace_id, session_id, tool, label, status, input_summary, output_summary, error, started_at, duration_ms),
    )
    return TraceSummary(
        trace_id=trace_id,
        tool=tool,
        label=label,
        status=status,
        started_at=started_at,
        duration_ms=duration_ms,
    )


def get_home() -> HomeResponse:
    with connect() as connection:
        session = connection.execute(
            "SELECT * FROM sessions WHERE learner_id = ? ORDER BY updated_at DESC LIMIT 1", (LEARNER_ID,)
        ).fetchone()
        profile = get_mastery_profile(connection)
        if profile is None:
            timestamp = now_iso()
            mastery = MasterySummary(
                knowledge_point_id=KNOWLEDGE_POINT_ID,
                knowledge_point_name=KNOWLEDGE_POINT_NAME,
                mastery_state="unassessed",
                evidence_level="none",
                reason="尚无作答证据。",
                updated_at=timestamp,
            )
        else:
            mastery = mastery_from_row(profile)

        if session is None:
            recommendation = Recommendation(
                knowledge_point_id=KNOWLEDGE_POINT_ID,
                title="从一次真实作答开始",
                reason="先了解你如何理解 range() 的起始值、停止值和步长。",
                action="start_session",
            )
        elif session["phase"] != "completed":
            recommendation = Recommendation(
                knowledge_point_id=KNOWLEDGE_POINT_ID,
                title="继续完成 range() 学习任务",
                reason="已有一段未完成的学习会话。",
                action="resume_session",
                session_id=session["id"],
            )
        elif mastery.mastery_state == "pending_verification":
            recommendation = Recommendation(
                knowledge_point_id=KNOWLEDGE_POINT_ID,
                title="完成一次独立迁移验证",
                reason="上次迁移使用了提示；新任务将不携带上次提示。",
                action="start_transfer_verification",
            )
        else:
            recommendation = Recommendation(
                knowledge_point_id=KNOWLEDGE_POINT_ID,
                title="回看本次掌握证据",
                reason=mastery.reason,
                action="review_evidence",
                session_id=session["id"],
            )
        return HomeResponse(
            learner=LearnerSummary(id=LEARNER_ID, display_name="体验学习者"),
            recommendation=recommendation,
            mastery=mastery,
        )


def create_session(knowledge_point_id: str) -> SessionEnvelope:
    if knowledge_point_id != KNOWLEDGE_POINT_ID:
        raise api_error(404, "KNOWLEDGE_POINT_NOT_FOUND", "v0.1 只提供 Python range() 学习任务。")
    session_id = new_id("session")
    timestamp = now_iso()
    with connect() as connection:
        profile = get_mastery_profile(connection)
        previous_session = connection.execute(
            """SELECT transfer_variant_id FROM sessions
               WHERE learner_id = ? AND knowledge_point_id = ?
               ORDER BY updated_at DESC LIMIT 1""",
            (LEARNER_ID, KNOWLEDGE_POINT_ID),
        ).fetchone()
        transfer_variant_id = (
            next_transfer_variant_id(previous_session["transfer_variant_id"])
            if previous_session is not None
            else DEFAULT_TRANSFER_VARIANT_ID
        )
        mastery_state = profile["mastery_state"] if profile else "unassessed"
        evidence_level = profile["evidence_level"] if profile else "none"
        mastery_reason = profile["mastery_reason"] if profile else "尚无作答证据。"
        phase = "transfer_check" if mastery_state == "pending_verification" else "diagnostic"
        connection.execute(
            """INSERT INTO sessions
               (id, learner_id, knowledge_point_id, phase, revision, current_hint_level,
                highest_hint_level, mastery_state, evidence_level, mastery_reason,
                transfer_variant_id, last_diagnosis_code, created_at, updated_at)
               VALUES (?, ?, ?, ?, 1, 0, 0, ?, ?, ?, ?, NULL, ?, ?)""",
            (
                session_id,
                LEARNER_ID,
                knowledge_point_id,
                phase,
                mastery_state,
                evidence_level,
                mastery_reason,
                transfer_variant_id,
                timestamp,
                timestamp,
            ),
        )
        if profile is None:
            save_mastery_profile(connection, mastery_state, evidence_level, mastery_reason, timestamp)
        row = connection.execute("SELECT * FROM sessions WHERE id = ?", (session_id,)).fetchone()
        trace = record_trace(
            connection,
            session_id,
            "create_learning_session",
            "建立学习会话",
            "Python range()",
            (
                f"进入迁移验证阶段，题目变式={transfer_variant_id}"
                if phase == "transfer_check"
                else f"进入诊断阶段，预留迁移变式={transfer_variant_id}"
            ),
        )
        return SessionEnvelope(
            session=session_from_row(connection, row),
            decision=decision_for_row(row),
            mastery=mastery_from_row(row),
            trace=[trace],
        )


def get_session(session_id: str) -> SessionEnvelope:
    with connect() as connection:
        row = connection.execute("SELECT * FROM sessions WHERE id = ?", (session_id,)).fetchone()
        if row is None:
            raise api_error(404, "SESSION_NOT_FOUND", "学习会话不存在。")
        return SessionEnvelope(
            session=session_from_row(connection, row),
            decision=decision_for_row(row),
            mastery=mastery_from_row(row),
        )


def require_current_session(connection, session_id: str, task_id: str, expected_revision: int):
    row = connection.execute("SELECT * FROM sessions WHERE id = ?", (session_id,)).fetchone()
    if row is None:
        raise api_error(404, "SESSION_NOT_FOUND", "学习会话不存在。")
    if row["revision"] != expected_revision:
        raise api_error(409, "STALE_SESSION_REVISION", "会话已在其他页面更新，请刷新后继续。")
    expected_task = task_for_phase(row["phase"], row["transfer_variant_id"])
    if expected_task.id != task_id:
        raise api_error(409, "TASK_MISMATCH", "当前任务已经变化，请刷新页面。")
    if row["phase"] == "completed":
        raise api_error(409, "TASK_MISMATCH", "本次学习会话已经完成。")
    return row


def submit_attempt(session_id: str, task_id: str, raw_answer: str, expected_revision: int) -> AttemptResponse:
    started = time.perf_counter()
    with connect() as connection:
        row = require_current_session(connection, session_id, task_id, expected_revision)
        traces: list[TraceSummary] = []
        try:
            if row["phase"] == "transfer_check":
                normalized, generated = parse_range_parameters(raw_answer)
                target_sequence = list(transfer_variant(row["transfer_variant_id"]).target_sequence)
                correct = generated == target_sequence
                diagnosis_code = None if correct else "TRANSFER_SEQUENCE_MISMATCH"
                diagnosis = (
                    "参数可以生成目标序列。" if correct else f"这组参数实际生成 {generated}，还没有得到目标序列。"
                )
                output_summary = f"生成序列 {generated}"
            else:
                normalized = parse_integer_list(raw_answer)
                correct = normalized == DIAGNOSTIC_EXPECTED
                diagnosis_code, diagnosis = diagnose_diagnostic_answer(normalized)
                output_summary = f"解析为 {normalized}"
        except AnswerFormatError as exc:
            record_trace(
                connection,
                session_id,
                "parse_answer",
                "解析答案",
                "学习者提交的文本",
                "未生成结构化答案",
                status="failed",
                error=str(exc),
                duration_ms=max(1, int((time.perf_counter() - started) * 1000)),
            )
            connection.commit()
            raise api_error(422, "INVALID_ANSWER_FORMAT", str(exc), field="answer") from exc

        traces.append(
            record_trace(
                connection,
                session_id,
                "parse_answer",
                "解析答案",
                "学习者提交的文本",
                output_summary,
                duration_ms=max(1, int((time.perf_counter() - started) * 1000)),
            )
        )

        hint_level = row["current_hint_level"]
        phase = row["phase"]
        mastery_state = row["mastery_state"]
        evidence_level = row["evidence_level"]
        mastery_reason = row["mastery_reason"]
        evidence_summary = None

        if phase == "transfer_check" and correct:
            phase = "completed"
            if hint_level == 0:
                mastery_state = "mastered"
                evidence_level = "transfer_verified"
                mastery_reason = "无提示完成迁移任务，已形成独立掌握证据。"
                evidence_summary = "无提示构造参数并生成目标序列。"
            else:
                mastery_state = "pending_verification"
                evidence_level = "assisted"
                mastery_reason = "迁移任务使用了提示，仍需独立完成一次迁移验证。"
                evidence_summary = f"使用 {hint_level} 级提示后完成迁移任务。"
        elif phase != "transfer_check" and correct:
            phase = "transfer_check"
            evidence_level = "independent" if hint_level == 0 else "assisted"
            mastery_state = "pending_verification"
            if hint_level == 0:
                mastery_reason = "当前题独立完成，仍需迁移任务验证。"
                evidence_summary = "独立完成诊断题。"
            else:
                mastery_reason = "当前题在提示后完成，仍需独立迁移验证。"
                evidence_summary = f"使用 {hint_level} 级提示后完成诊断题。"
        elif not correct:
            phase = "guided_practice" if phase != "transfer_check" else "transfer_check"
            mastery_state = "learning"
            mastery_reason = diagnosis

        timestamp = now_iso()
        attempt_id = new_id("attempt")
        connection.execute(
            """INSERT INTO attempts
               (id, session_id, task_id, raw_answer, normalized_answer, correct, hint_level,
                diagnosis_code, diagnosis, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                attempt_id,
                session_id,
                task_id,
                raw_answer,
                json.dumps(normalized, ensure_ascii=False),
                int(correct),
                hint_level,
                diagnosis_code,
                diagnosis,
                timestamp,
            ),
        )
        next_hint_level = 0 if correct else hint_level
        next_diagnosis_code = None if correct else diagnosis_code
        connection.execute(
            """UPDATE sessions
               SET phase = ?, revision = revision + 1, current_hint_level = ?,
                    mastery_state = ?, evidence_level = ?, mastery_reason = ?,
                    last_diagnosis_code = ?, updated_at = ?
               WHERE id = ?""",
            (
                phase,
                next_hint_level,
                mastery_state,
                evidence_level,
                mastery_reason,
                next_diagnosis_code,
                timestamp,
                session_id,
            ),
        )
        save_mastery_profile(connection, mastery_state, evidence_level, mastery_reason, timestamp)
        if evidence_summary is not None:
            connection.execute(
                """INSERT INTO evidence
                   (id, session_id, task_id, level, correct, hint_level, summary, created_at)
                   VALUES (?, ?, ?, ?, 1, ?, ?, ?)""",
                (new_id("evidence"), session_id, task_id, evidence_level, hint_level, evidence_summary, timestamp),
            )
        traces.append(
            record_trace(
                connection,
                session_id,
                "diagnose_misconception" if task_id == "range-diagnostic-01" else "verify_transfer",
                "识别错因" if task_id == "range-diagnostic-01" else "验证迁移",
                "已规范化答案",
                diagnosis,
            )
        )
        traces.append(
            record_trace(
                connection,
                session_id,
                "decide_next_action",
                "决定下一步",
                f"作答正确={correct}，提示等级={hint_level}",
                f"进入 {phase} 阶段，掌握状态={mastery_state}",
            )
        )
        updated = connection.execute("SELECT * FROM sessions WHERE id = ?", (session_id,)).fetchone()
        return AttemptResponse(
            attempt=AttemptView(
                id=attempt_id,
                normalized_answer=normalized,
                correct=correct,
                assistance_level=hint_level,
                diagnosis_code=diagnosis_code,
                diagnosis=diagnosis,
            ),
            session=session_from_row(connection, updated),
            decision=decision_for_row(updated) if correct else AgentDecision(
                action="retry_or_request_hint",
                title="先修正当前理解",
                reason_codes=[diagnosis_code or "SEQUENCE_MISMATCH"],
                reason_summary=diagnosis,
                mastery_effect="no_change",
                next_step="重新尝试，或在需要时请求一级提示。",
            ),
            mastery=mastery_from_row(updated),
            trace=traces,
        )


def request_hint(session_id: str, task_id: str, expected_revision: int) -> SessionEnvelope:
    with connect() as connection:
        row = require_current_session(connection, session_id, task_id, expected_revision)
        next_level = min(row["current_hint_level"] + 1, 3)
        timestamp = now_iso()
        connection.execute(
            """UPDATE sessions
               SET current_hint_level = ?, highest_hint_level = MAX(highest_hint_level, ?),
                   revision = revision + 1, updated_at = ? WHERE id = ?""",
            (next_level, next_level, timestamp, session_id),
        )
        updated = connection.execute("SELECT * FROM sessions WHERE id = ?", (session_id,)).fetchone()
        trace = record_trace(
            connection,
            session_id,
            "select_hint",
            "选择提示",
            (
                f"当前阶段={row['phase']}，已有提示等级={row['current_hint_level']}，"
                f"诊断码={row['last_diagnosis_code'] or 'NONE'}"
            ),
            f"提供 {next_level} 级提示，题目变式={row['transfer_variant_id']}",
        )
        return SessionEnvelope(
            session=session_from_row(connection, updated),
            decision=AgentDecision(
                action="retry_with_hint",
                title=f"使用 {next_level} 级提示继续思考",
                reason_codes=["HINT_REQUESTED"],
                reason_summary="提示只增加当前需要的信息，不直接给出答案。",
                mastery_effect="no_change",
                next_step="结合提示重新提交答案。",
            ),
            mastery=mastery_from_row(updated),
            trace=[trace],
        )


def get_evidence(knowledge_point_id: str) -> EvidenceResponse:
    if knowledge_point_id != KNOWLEDGE_POINT_ID:
        raise api_error(404, "KNOWLEDGE_POINT_NOT_FOUND", "知识点不存在。")
    with connect() as connection:
        profile = get_mastery_profile(connection)
        if profile is None:
            timestamp = now_iso()
            mastery = MasterySummary(
                knowledge_point_id=KNOWLEDGE_POINT_ID,
                knowledge_point_name=KNOWLEDGE_POINT_NAME,
                mastery_state="unassessed",
                evidence_level="none",
                reason="尚无作答证据。",
                updated_at=timestamp,
            )
            return EvidenceResponse(mastery=mastery, required_next_evidence="完成一次诊断作答。", items=[])
        rows = connection.execute(
            """SELECT evidence.* FROM evidence
               JOIN sessions ON sessions.id = evidence.session_id
               WHERE sessions.learner_id = ? AND sessions.knowledge_point_id = ?
               ORDER BY evidence.created_at DESC""",
            (LEARNER_ID, KNOWLEDGE_POINT_ID),
        ).fetchall()
        required = None
        if profile["mastery_state"] != "mastered":
            required = "在不使用提示的情况下完成迁移题。"
        return EvidenceResponse(
            mastery=mastery_from_row(profile),
            required_next_evidence=required,
            items=[
                EvidenceItem(
                    evidence_id=row["id"],
                    session_id=row["session_id"],
                    task_id=row["task_id"],
                    evidence_level=row["level"],
                    correct=bool(row["correct"]),
                    hint_level=row["hint_level"],
                    summary=row["summary"],
                    created_at=row["created_at"],
                )
                for row in rows
            ],
        )


def get_trace(session_id: str) -> TraceResponse:
    with connect() as connection:
        exists = connection.execute("SELECT 1 FROM sessions WHERE id = ?", (session_id,)).fetchone()
        if exists is None:
            raise api_error(404, "SESSION_NOT_FOUND", "学习会话不存在。")
        rows = connection.execute(
            "SELECT * FROM traces WHERE session_id = ? ORDER BY started_at", (session_id,)
        ).fetchall()
        return TraceResponse(
            session_id=session_id,
            items=[
                TraceItem(
                    trace_id=row["id"],
                    tool=row["tool"],
                    label=row["label"],
                    status=row["status"],
                    input_summary=row["input_summary"],
                    output_summary=row["output_summary"],
                    error=row["error"],
                    started_at=row["started_at"],
                    duration_ms=row["duration_ms"],
                )
                for row in rows
            ],
        )

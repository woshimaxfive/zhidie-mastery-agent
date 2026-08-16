from __future__ import annotations

import sqlite3
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .database import init_database
from .schemas import (
    AttemptRequest,
    AttemptResponse,
    CreateSessionRequest,
    EvidenceResponse,
    HintRequest,
    HomeResponse,
    SessionEnvelope,
    TraceResponse,
)
from .service import create_session, get_evidence, get_home, get_session, get_trace, request_hint, submit_attempt


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_database()
    yield


app = FastAPI(
    title="知迭 MasteryAgent API",
    version="0.1.0",
    description="掌握学习闭环的确定性领域 API。",
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


def error_payload(
    code: str,
    message: str,
    *,
    retryable: bool,
    field: str | None = None,
    details: dict | None = None,
) -> dict:
    return {
        "error": {
            "code": code,
            "message": message,
            "retryable": retryable,
            "field": field,
            "request_id": f"req_{uuid.uuid4().hex[:12]}",
            "details": details or {},
        }
    }


@app.exception_handler(HTTPException)
async def http_exception_handler(_: Request, exc: HTTPException):
    detail = exc.detail if isinstance(exc.detail, dict) else {
        "code": "HTTP_ERROR",
        "message": str(exc.detail),
        "retryable": False,
        "field": None,
        "request_id": "unknown",
        "details": {},
    }
    return JSONResponse(status_code=exc.status_code, content={"error": detail})


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(_: Request, exc: RequestValidationError):
    issues = []
    for issue in exc.errors():
        location = [str(part) for part in issue.get("loc", []) if part != "body"]
        issues.append({"field": ".".join(location) or None, "type": issue.get("type", "validation_error")})
    field = issues[0]["field"] if issues else None
    return JSONResponse(
        status_code=422,
        content=error_payload(
            "INVALID_REQUEST",
            "请求参数不符合接口要求。",
            retryable=False,
            field=field,
            details={"issues": issues},
        ),
    )


@app.exception_handler(sqlite3.Error)
async def persistence_exception_handler(_: Request, __: sqlite3.Error):
    return JSONResponse(
        status_code=503,
        content=error_payload(
            "PERSISTENCE_FAILED",
            "本地学习记录暂时无法读取或保存，请重试。",
            retryable=True,
        ),
    )


@app.exception_handler(Exception)
async def internal_exception_handler(_: Request, __: Exception):
    return JSONResponse(
        status_code=500,
        content=error_payload(
            "INTERNAL_ERROR",
            "服务发生未分类错误，请稍后重试。",
            retryable=True,
        ),
    )


@app.get("/api/v1/health")
def health() -> dict[str, str]:
    return {"status": "ok", "mode": "offline-deterministic"}


@app.get("/api/v1/home", response_model=HomeResponse)
def home() -> HomeResponse:
    return get_home()


@app.post("/api/v1/sessions", response_model=SessionEnvelope, status_code=201)
def sessions_create(payload: CreateSessionRequest) -> SessionEnvelope:
    return create_session(payload.knowledge_point_id)


@app.get("/api/v1/sessions/{session_id}", response_model=SessionEnvelope)
def sessions_get(session_id: str) -> SessionEnvelope:
    return get_session(session_id)


@app.post("/api/v1/sessions/{session_id}/attempts", response_model=AttemptResponse)
def attempts_create(session_id: str, payload: AttemptRequest) -> AttemptResponse:
    return submit_attempt(session_id, payload.task_id, payload.answer, payload.expected_revision)


@app.post("/api/v1/sessions/{session_id}/hints", response_model=SessionEnvelope)
def hints_create(session_id: str, payload: HintRequest) -> SessionEnvelope:
    return request_hint(session_id, payload.task_id, payload.expected_revision)


@app.get(
    "/api/v1/knowledge-points/{knowledge_point_id}/evidence",
    response_model=EvidenceResponse,
)
def evidence_get(knowledge_point_id: str) -> EvidenceResponse:
    return get_evidence(knowledge_point_id)


@app.get("/api/v1/sessions/{session_id}/trace", response_model=TraceResponse)
def trace_get(session_id: str) -> TraceResponse:
    return get_trace(session_id)

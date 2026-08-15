import type {
  AttemptResponse,
  EvidenceResponse,
  HomeResponse,
  SessionEnvelope,
  TraceItem,
} from "./types";

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? "http://127.0.0.1:8000/api/v1";

export class ApiError extends Error {
  code: string;
  retryable: boolean;

  constructor(message: string, code = "NETWORK_ERROR", retryable = true) {
    super(message);
    this.name = "ApiError";
    this.code = code;
    this.retryable = retryable;
  }
}

function readApiError(payload: unknown): { message?: string; code?: string; retryable?: boolean } | null {
  if (payload === null || typeof payload !== "object") return null;
  const error = (payload as Record<string, unknown>).error;
  if (error === null || typeof error !== "object") return null;
  const candidate = error as Record<string, unknown>;
  return {
    message: typeof candidate.message === "string" ? candidate.message : undefined,
    code: typeof candidate.code === "string" ? candidate.code : undefined,
    retryable: typeof candidate.retryable === "boolean" ? candidate.retryable : undefined,
  };
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${API_BASE}${path}`, {
      ...init,
      headers: { "Content-Type": "application/json", ...init?.headers },
    });
  } catch {
    throw new ApiError("无法连接学习服务。请确认后端已经启动，然后重试。", "NETWORK_ERROR", true);
  }
  if (!response.ok) {
    const payload: unknown = await response.json().catch(() => null);
    const apiError = readApiError(payload);
    throw new ApiError(
      apiError?.message ?? "请求未完成，请检查输入后重试。",
      apiError?.code ?? "HTTP_ERROR",
      apiError?.retryable ?? response.status >= 500,
    );
  }
  return (await response.json()) as T;
}

export const api = {
  home: () => request<HomeResponse>("/home"),
  createSession: () =>
    request<SessionEnvelope>("/sessions", {
      method: "POST",
      body: JSON.stringify({ knowledge_point_id: "python.range" }),
    }),
  session: (sessionId: string) => request<SessionEnvelope>(`/sessions/${sessionId}`),
  submitAttempt: (sessionId: string, taskId: string, answer: string, revision: number) =>
    request<AttemptResponse>(`/sessions/${sessionId}/attempts`, {
      method: "POST",
      body: JSON.stringify({ task_id: taskId, answer, expected_revision: revision }),
    }),
  requestHint: (sessionId: string, taskId: string, revision: number) =>
    request<SessionEnvelope>(`/sessions/${sessionId}/hints`, {
      method: "POST",
      body: JSON.stringify({ task_id: taskId, expected_revision: revision }),
    }),
  evidence: (knowledgePointId: string) =>
    request<EvidenceResponse>(`/knowledge-points/${encodeURIComponent(knowledgePointId)}/evidence`),
  trace: async (sessionId: string) => {
    const response = await request<{ session_id: string; items: TraceItem[] }>(`/sessions/${sessionId}/trace`);
    return response.items;
  },
};

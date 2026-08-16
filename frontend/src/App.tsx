import { useEffect, useRef, useState } from "react";
import { Link, Route, Routes, useNavigate, useParams, useSearchParams } from "react-router-dom";
import { ApiError, api } from "./api";
import type {
  AttemptResponse,
  EvidenceLevel,
  EvidenceResponse,
  HomeResponse,
  MasteryState,
  SessionEnvelope,
  SessionPhase,
  TraceItem,
} from "./types";

const PHASES: Array<{ key: SessionPhase; label: string }> = [
  { key: "diagnostic", label: "诊断" },
  { key: "guided_practice", label: "引导" },
  { key: "transfer_check", label: "迁移" },
  { key: "completed", label: "结论" },
];

const PHASE_ORDER: Record<SessionPhase, number> = {
  diagnostic: 0,
  guided_practice: 1,
  transfer_check: 2,
  completed: 3,
};

const MASTERY_LABELS: Record<MasteryState, string> = {
  unassessed: "尚未评估",
  learning: "学习中",
  pending_verification: "待独立验证",
  mastered: "已掌握",
};

const EVIDENCE_LABELS: Record<EvidenceLevel, string> = {
  none: "暂无证据",
  assisted: "辅助完成",
  independent: "独立作答",
  transfer_verified: "迁移已验证",
};

const LOOP_STEPS = [
  { number: "01", title: "诊断理解", description: "从真实作答识别具体错因" },
  { number: "02", title: "渐进引导", description: "只提供当前需要的一层提示" },
  { number: "03", title: "迁移验证", description: "换一种任务确认能够独立应用" },
  { number: "04", title: "更新证据", description: "依据行为记录决定下一步" },
] as const;

// 掌握状态到闭环步骤的映射：让首页四步显示学习者当前所处环节，而不是一段静态说明。
const ACTIVE_LOOP_STEP: Record<MasteryState, number> = {
  unassessed: 0,
  learning: 1,
  pending_verification: 2,
  mastered: 3,
};

function Shell({ children }: { children: React.ReactNode }) {
  return (
    <div className="app-shell">
      <header className="site-header">
        <Link to="/" className="brand" aria-label="知迭首页">
          <span className="brand-mark" aria-hidden="true">迭</span>
          <span>
            <strong>知迭</strong>
            <small>MasteryAgent</small>
          </span>
        </Link>
        <nav aria-label="主导航">
          <Link to="/">学习首页</Link>
          <Link to="/evidence/python.range">掌握证据</Link>
        </nav>
      </header>
      {children}
    </div>
  );
}

function LoadingState({ label = "正在读取学习状态" }: { label?: string }) {
  return <div className="state-panel" role="status"><span className="pulse-dot" />{label}</div>;
}

function ErrorState({ id, message, onRetry }: { id?: string; message: string; onRetry?: () => void }) {
  return (
    <div id={id} className="state-panel error-state" role="alert">
      <strong>本次操作没有完成</strong>
      <p>{message}</p>
      {onRetry && <button className="button secondary" onClick={onRetry}>重新尝试</button>}
    </div>
  );
}

function MasteryBadge({ state }: { state: MasteryState }) {
  return <span className={`status-badge status-${state}`}>{MASTERY_LABELS[state]}</span>;
}

function HomePage() {
  const navigate = useNavigate();
  const [data, setData] = useState<HomeResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const load = () => {
    setError(null);
    api.home().then(setData).catch((reason: ApiError) => setError(reason.message));
  };

  useEffect(load, []);

  const startNewSession = async () => {
    setBusy(true);
    setError(null);
    try {
      const created = await api.createSession();
      navigate(`/learn/${created.session.session_id}`);
    } catch (reason) {
      setError(reason instanceof ApiError ? reason.message : "无法建立学习会话。请稍后重试。");
      setBusy(false);
    }
  };

  const continueLearning = async () => {
    if (!data) return;
    if (data.recommendation.action === "review_evidence") {
      const knowledgePointId = encodeURIComponent(data.recommendation.knowledge_point_id);
      navigate(`/evidence/${knowledgePointId}?session=${data.recommendation.session_id ?? ""}`);
      return;
    }
    if (data.recommendation.action === "resume_session" && data.recommendation.session_id) {
      navigate(`/learn/${data.recommendation.session_id}`);
      return;
    }
    await startNewSession();
  };

  return (
    <Shell>
      <main className="home-page">
        {!data && !error && <LoadingState />}
        {error && <ErrorState message={error} onRetry={load} />}
        {data && (
          <>
            <section className="home-intro" aria-labelledby="home-title">
              <p className="eyebrow">今天的学习起点</p>
              <h1 id="home-title">{data.recommendation.title}</h1>
              <p className="lead">{data.recommendation.reason}</p>
              <div className="home-actions">
                <button className="button primary" onClick={continueLearning} disabled={busy}>
                  {busy
                    ? "正在建立会话…"
                    : data.recommendation.action === "start_session"
                      ? "开始诊断"
                      : data.recommendation.action === "start_transfer_verification"
                        ? "开始迁移验证"
                        : data.recommendation.action === "resume_session"
                          ? "继续学习"
                          : "查看掌握证据"}
                </button>
                {data.mastery.mastery_state === "mastered" && (
                  <button className="button secondary" onClick={startNewSession} disabled={busy}>
                    再练一次
                  </button>
                )}
              </div>
            </section>

            <section className="home-evidence" aria-labelledby="evidence-summary-title">
              <div className="section-heading">
                <p className="eyebrow">当前依据</p>
                <MasteryBadge state={data.mastery.mastery_state} />
              </div>
              <h2 id="evidence-summary-title">Python · range()</h2>
              <p>{data.mastery.reason}</p>
              <div className="evidence-level-row">
                <span>证据等级</span>
                <strong>{EVIDENCE_LABELS[data.mastery.evidence_level]}</strong>
              </div>
              <Link className="text-link" to={`/evidence/${encodeURIComponent(data.mastery.knowledge_point_id)}`}>查看完整证据 →</Link>
            </section>

            {/* 四步不是静态说明：按当前掌握状态标出学习者所处的环节，让首页反映真实进度。 */}
            <section className="learning-path" aria-label="掌握学习路径">
              {LOOP_STEPS.map((step, index) => {
                const activeIndex = ACTIVE_LOOP_STEP[data.mastery.mastery_state];
                const state = index === activeIndex ? "current" : index < activeIndex ? "done" : "upcoming";
                return (
                  <article key={step.number} className={state} aria-current={state === "current" || undefined}>
                    <span>{step.number}</span>
                    <h3>{step.title}</h3>
                    <p>{step.description}</p>
                  </article>
                );
              })}
            </section>
          </>
        )}
      </main>
    </Shell>
  );
}

function PhaseRail({ current }: { current: SessionPhase }) {
  const currentIndex = PHASE_ORDER[current];
  return (
    <ol className="phase-rail" aria-label="学习阶段">
      {PHASES.map((phase, index) => (
        <li key={phase.key} className={index < currentIndex ? "done" : index === currentIndex ? "current" : ""}>
          <span aria-hidden="true">{index < currentIndex ? "✓" : index + 1}</span>
          {phase.label}
        </li>
      ))}
    </ol>
  );
}

// 展开学习者本次作答的每一项取值。答错时展示的是学习者自己的理解，不是正确执行结果，
// 因此标题和节点配色都要与"正确"区分开，否则会被误读成系统在演示标准答案。
function ExecutionTape({ feedback }: { feedback: AttemptResponse["attempt"] | null }) {
  const sequence = feedback?.normalized_answer ?? [];
  const showsLearnerError = feedback !== null && !feedback.correct;
  const showsIncludedBoundary = feedback?.diagnosis_code === "STOP_VALUE_INCLUDED";
  const displayedSequence = showsIncludedBoundary ? sequence.slice(0, -1) : sequence;

  const title = showsLearnerError ? "你的理解展开" : "执行轨迹";
  const note = showsLearnerError
    ? "这是你本次答案的展开，不是正确执行结果"
    : feedback
      ? "与正确执行一致"
      : "提交后显示执行关系";

  return (
    <section className={`execution-tape${showsLearnerError ? " learner-error" : ""}`} aria-labelledby="execution-title">
      <div className="tape-label">
        <span>{title}</span>
        <small>{note}</small>
      </div>
      <h2 id="execution-title" className="sr-only">{title}</h2>
      {displayedSequence.length === 0 ? (
        <p className="tape-empty">提交答案后，这里会按步展开每一项的取值。</p>
      ) : (
        <div className="tape-scroll" role="region" aria-label={`可横向滚动的${title}`} tabIndex={0}>
          <div className="tape-track">
            {displayedSequence.map((value, index) => (
              <div className="tape-step" key={`${value}-${index}`}>
                <span className={showsLearnerError ? "value-node learner-node" : "value-node"}>{value}</span>
                {index < displayedSequence.length - 1 && <i aria-hidden="true" />}
              </div>
            ))}
            {showsIncludedBoundary && (
              <div className="boundary-node"><span>10</span><small>停止边界</small></div>
            )}
          </div>
        </div>
      )}
    </section>
  );
}

function LearnPage() {
  const { sessionId = "" } = useParams();
  const navigate = useNavigate();
  const [envelope, setEnvelope] = useState<SessionEnvelope | null>(null);
  const [answer, setAnswer] = useState("");
  const [feedback, setFeedback] = useState<AttemptResponse["attempt"] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [answerError, setAnswerError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [traceOpen, setTraceOpen] = useState(false);
  const [trace, setTrace] = useState<TraceItem[]>([]);
  const [traceError, setTraceError] = useState<string | null>(null);
  const answerInputRef = useRef<HTMLInputElement>(null);
  const traceTriggerRef = useRef<HTMLButtonElement>(null);
  const traceDrawerRef = useRef<HTMLElement>(null);

  const load = () => {
    setError(null);
    api.session(sessionId).then(setEnvelope).catch((reason: ApiError) => setError(reason.message));
  };

  useEffect(load, [sessionId]);

  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!envelope || !answer.trim()) return;
    setBusy(true);
    setAnswerError(null);
    try {
      const response = await api.submitAttempt(
        sessionId,
        envelope.session.task.id,
        answer.trim(),
        envelope.session.revision,
      );
      setFeedback(response.attempt);
      setEnvelope(response);
      setAnswer("");
    } catch (reason) {
      setAnswerError(reason instanceof ApiError ? reason.message : "作答未能提交，请重新尝试。");
      requestAnimationFrame(() => answerInputRef.current?.focus());
    } finally {
      setBusy(false);
    }
  };

  const askForHint = async () => {
    if (!envelope) return;
    setBusy(true);
    setError(null);
    try {
      const response = await api.requestHint(
        sessionId,
        envelope.session.task.id,
        envelope.session.revision,
      );
      setEnvelope(response);
    } catch (reason) {
      setError(reason instanceof ApiError ? reason.message : "提示暂时无法加载。");
    } finally {
      setBusy(false);
    }
  };

  const openTrace = async () => {
    setTrace([]);
    setTraceError(null);
    setTraceOpen(true);
    try {
      setTrace(await api.trace(sessionId));
    } catch (reason) {
      setTraceError(reason instanceof ApiError ? reason.message : "执行记录暂时无法读取。");
    }
  };

  const closeTrace = () => {
    setTraceOpen(false);
    requestAnimationFrame(() => traceTriggerRef.current?.focus());
  };

  useEffect(() => {
    if (!traceOpen) return;
    const drawer = traceDrawerRef.current;
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";

    const focusableSelector = [
      "a[href]",
      "button:not([disabled])",
      "input:not([disabled])",
      "select:not([disabled])",
      "textarea:not([disabled])",
      "[tabindex]:not([tabindex='-1'])",
    ].join(",");
    const getFocusable = () => Array.from(drawer?.querySelectorAll<HTMLElement>(focusableSelector) ?? []);
    requestAnimationFrame(() => getFocusable()[0]?.focus());

    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        event.preventDefault();
        closeTrace();
        return;
      }
      if (event.key !== "Tab") return;
      const focusable = getFocusable();
      if (focusable.length === 0) {
        event.preventDefault();
        drawer?.focus();
        return;
      }
      const first = focusable[0];
      const last = focusable[focusable.length - 1];
      if (event.shiftKey && (document.activeElement === first || !drawer?.contains(document.activeElement))) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && (document.activeElement === last || !drawer?.contains(document.activeElement))) {
        event.preventDefault();
        first.focus();
      }
    };

    document.addEventListener("keydown", handleKeyDown);
    return () => {
      document.removeEventListener("keydown", handleKeyDown);
      document.body.style.overflow = previousOverflow;
    };
  }, [traceOpen]);

  if (!envelope && !error) return <Shell><main className="page-frame"><LoadingState /></main></Shell>;
  if (!envelope && error) return <Shell><main className="page-frame"><ErrorState message={error} onRetry={load} /></main></Shell>;
  if (!envelope) return null;

  const task = envelope.session.task;
  const completed = envelope.session.session_phase === "completed";
  const placeholder = task.kind === "sequence_prediction" ? "例如：[2, 5, 8]" : "例如：range(1, 11, 3)";

  return (
    <Shell>
      <main className="learn-page">
        <div className="learn-heading">
          <div>
            <p className="eyebrow">Python 基础 · range()</p>
            <h1>{completed ? "本次学习结论" : task.kind === "sequence_prediction" ? "先让代码在脑中运行一次" : "把理解迁移到新的任务"}</h1>
          </div>
          <PhaseRail current={envelope.session.session_phase} />
        </div>

        <div className="workspace-grid">
          <section className="task-workspace" aria-labelledby="task-title">
            {!completed && (
              <>
                <div className="task-copy">
                  <p className="eyebrow">当前任务</p>
                  <h2 id="task-title">{task.prompt}</h2>
                  {task.code && <pre><code>{task.code}</code></pre>}
                  {task.target_sequence && <div className="target-sequence">目标序列 <strong>[{task.target_sequence.join(", ")}]</strong></div>}
                </div>

                {/* 迁移阶段的目标序列已在任务描述中给出，此处只为诊断阶段展开学习者自己的作答。 */}
                {task.kind === "sequence_prediction" && <ExecutionTape feedback={feedback} />}

                {feedback && (
                  <div className={`feedback ${feedback.correct ? "correct" : "needs-work"}`} role="status">
                    <span>{feedback.correct ? "本步正确" : "发现一个具体问题"}</span>
                    <strong>{feedback.diagnosis}</strong>
                  </div>
                )}

                {/* 已解锁的提示全部保留，让"渐进"这一层层加信息的过程可以被回看和复查。 */}
                {envelope.session.hint_history.length > 0 && (
                  <div className="hint-stack" role="status">
                    {envelope.session.hint_history.map((item) => (
                      <div
                        key={item.level}
                        className={`hint-panel${item.level === envelope.session.hint?.level ? " latest" : " earlier"}`}
                      >
                        <span>{item.level} 级提示</span>
                        <p>{item.content}</p>
                      </div>
                    ))}
                  </div>
                )}

                {error && <ErrorState message={error} />}

                <form className="answer-form" onSubmit={submit}>
                  {answerError && <ErrorState id="answer-error" message={answerError} />}
                  <label htmlFor="answer">你的答案</label>
                  <div className="answer-row">
                    <input
                      ref={answerInputRef}
                      id="answer"
                      value={answer}
                      onChange={(event) => {
                        setAnswer(event.target.value);
                        if (answerError) setAnswerError(null);
                      }}
                      placeholder={placeholder}
                      autoComplete="off"
                      disabled={busy}
                      aria-invalid={Boolean(answerError)}
                      aria-describedby={answerError ? "answer-note answer-error" : "answer-note"}
                      aria-errormessage={answerError ? "answer-error" : undefined}
                    />
                    <button className="button primary" disabled={busy || !answer.trim()}>
                      {busy ? "正在判断…" : "提交答案"}
                    </button>
                  </div>
                  <div className="answer-actions">
                    <small id="answer-note">系统会执行和验证你的输入，不要求唯一文本形式。</small>
                    <button type="button" className="text-button" onClick={askForHint} disabled={busy || envelope.session.hint?.level === 3}>
                      {envelope.session.hint?.level === 3 ? "已提供最高级提示" : "我需要一点提示"}
                    </button>
                  </div>
                </form>
              </>
            )}

            {completed && (
              <section className={`completion ${envelope.mastery.mastery_state === "mastered" ? "verified" : "pending"}`}>
                <p className="eyebrow">掌握证据更新</p>
                <MasteryBadge state={envelope.mastery.mastery_state} />
                <h2>{envelope.decision.title}</h2>
                <p>{envelope.mastery.reason}</p>
                <button
                  className="button primary"
                  onClick={() => navigate(
                    `/evidence/${encodeURIComponent(envelope.mastery.knowledge_point_id)}?session=${sessionId}`,
                  )}
                >
                  查看证据链
                </button>
              </section>
            )}
          </section>

          <aside className="decision-panel" aria-labelledby="decision-title">
            <p className="eyebrow">Agent 当前决定</p>
            <h2 id="decision-title">{envelope.decision.title}</h2>
            <p>{envelope.decision.reason_summary}</p>
            <hr className="decision-rule" />
            <dl>
              <div><dt>正式状态</dt><dd><MasteryBadge state={envelope.mastery.mastery_state} /></dd></div>
              <div><dt>状态依据</dt><dd>{envelope.mastery.reason}</dd></div>
              <div><dt>下一步</dt><dd>{envelope.decision.next_step}</dd></div>
            </dl>
            <button ref={traceTriggerRef} className="button ghost" onClick={openTrace}>查看执行记录</button>
          </aside>
        </div>
      </main>

      {traceOpen && (
        <div className="drawer-backdrop" onMouseDown={closeTrace}>
          <aside
            ref={traceDrawerRef}
            className="trace-drawer"
            role="dialog"
            aria-modal="true"
            aria-labelledby="trace-title"
            tabIndex={-1}
            onMouseDown={(event) => event.stopPropagation()}
          >
            <div className="drawer-heading">
              <div><p className="eyebrow">可追溯过程</p><h2 id="trace-title">Agent 执行记录</h2></div>
              <button className="icon-button" onClick={closeTrace} aria-label="关闭执行记录">×</button>
            </div>
            {traceError ? <ErrorState message={traceError} onRetry={openTrace} /> : trace.length === 0 ? <LoadingState label="正在读取执行记录" /> : (
              <ol className="trace-list">
                {trace.map((item) => (
                  <li key={item.trace_id}>
                    <span className={`trace-status ${item.status}`} />
                    <div>
                      <strong>{item.label}</strong>
                      <small>{item.tool} · {item.duration_ms} ms</small>
                      <p>{item.output_summary}</p>
                      {item.error && <p className="trace-error">{item.error}</p>}
                    </div>
                  </li>
                ))}
              </ol>
            )}
            <p className="privacy-note">记录仅展示工具输入与结果摘要，不包含模型思维链或敏感数据。</p>
          </aside>
        </div>
      )}
    </Shell>
  );
}

function EvidencePage() {
  const { knowledgeId = "" } = useParams();
  const [searchParams] = useSearchParams();
  const sessionId = searchParams.get("session");
  const [data, setData] = useState<EvidenceResponse | null>(null);
  const [trace, setTrace] = useState<TraceItem[]>([]);
  const [error, setError] = useState<string | null>(null);

  const load = () => {
    setError(null);
    Promise.all([api.evidence(knowledgeId), sessionId ? api.trace(sessionId) : Promise.resolve([])])
      .then(([evidence, traceItems]) => {
        setData(evidence);
        setTrace(traceItems);
      })
      .catch((reason: ApiError) => setError(reason.message));
  };

  useEffect(load, [knowledgeId, sessionId]);

  return (
    <Shell>
      <main className="evidence-page">
        {!data && !error && <LoadingState label="正在整理掌握证据" />}
        {error && <ErrorState message={error} onRetry={load} />}
        {data && (
          <>
            <header className="evidence-heading">
              <div>
                <p className="eyebrow">{data.mastery.knowledge_point_name}</p>
                <h1>掌握不是一次答对，<br />而是一条能够复查的证据链。</h1>
              </div>
              <div className="mastery-verdict">
                <MasteryBadge state={data.mastery.mastery_state} />
                <strong>{EVIDENCE_LABELS[data.mastery.evidence_level]}</strong>
                <p>{data.mastery.reason}</p>
              </div>
            </header>

            {data.required_next_evidence && (
              <section className="next-evidence">
                <span>下一条所需证据</span>
                <strong>{data.required_next_evidence}</strong>
              </section>
            )}

            <div className="evidence-grid">
              <section aria-labelledby="ledger-title">
                <p className="eyebrow">证据账本</p>
                <h2 id="ledger-title">本次状态由什么构成</h2>
                {data.items.length === 0 ? (
                  <div className="empty-evidence"><p>还没有形成正式证据。</p><Link className="button primary" to="/">开始第一次诊断</Link></div>
                ) : (
                  <ol className="evidence-list">
                    {data.items.map((item) => (
                      <li key={item.evidence_id}>
                        <span className={`evidence-dot evidence-${item.evidence_level}`} />
                        <div>
                          <small>{new Date(item.created_at).toLocaleString("zh-CN")}</small>
                          <strong>{item.summary}</strong>
                          <p>{EVIDENCE_LABELS[item.evidence_level]} · 提示等级 {item.hint_level}</p>
                        </div>
                      </li>
                    ))}
                  </ol>
                )}
              </section>

              <section aria-labelledby="trace-title">
                <p className="eyebrow">决策记录</p>
                <h2 id="trace-title">Agent 做过哪些检查</h2>
                {trace.length === 0 ? <p className="muted">从学习会话进入此页后，可查看对应的执行摘要。</p> : (
                  <ol className="compact-trace">
                    {trace.map((item) => (
                      <li key={item.trace_id}><span>{item.label}</span><strong>{item.output_summary}</strong></li>
                    ))}
                  </ol>
                )}
              </section>
            </div>
          </>
        )}
      </main>
    </Shell>
  );
}

function NotFoundPage() {
  return <Shell><main className="page-frame"><ErrorState message="这个页面不存在。请返回学习首页继续。" /><Link className="button primary" to="/">返回首页</Link></main></Shell>;
}

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<HomePage />} />
      <Route path="/learn/:sessionId" element={<LearnPage />} />
      <Route path="/evidence/:knowledgeId" element={<EvidencePage />} />
      <Route path="*" element={<NotFoundPage />} />
    </Routes>
  );
}

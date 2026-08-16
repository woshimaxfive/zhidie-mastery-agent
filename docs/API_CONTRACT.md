# 知迭 v0.1 API 契约

状态：v0.1

## 1. 原则

- 前端只通过 API 读取和提交领域状态，不在浏览器中复制掌握判定规则。
- 后端是会话、证据、掌握状态和 Agent Trace 的事实来源。
- v0.1 API 使用 `/api/v1` 前缀。
- 所有时间使用 ISO 8601 UTC 字符串。
- 所有标识符使用不透明字符串，前端不得解析其结构。
- 写请求携带 `expected_revision`，防止两个页面覆盖同一会话的新状态。

## 2. 共享枚举

```text
session_phase:
  diagnostic | guided_practice | transfer_check | completed

mastery_state:
  unassessed | learning | pending_verification | mastered

evidence_level:
  none | assisted | independent | transfer_verified

trace_status:
  succeeded | failed | skipped
```

枚举发生变化时，必须同时更新产品需求、前端类型和后端模型。

## 3. 公共数据结构

### `MasterySummary`

```json
{
  "knowledge_point_id": "python.range",
  "knowledge_point_name": "Python range()",
  "mastery_state": "learning",
  "evidence_level": "assisted",
  "reason": "当前正确作答使用了一级提示，仍需独立迁移验证。",
  "updated_at": "2026-08-15T10:00:00Z"
}
```

### `AgentDecision`

```json
{
  "action": "offer_hint",
  "title": "先澄清停止值规则",
  "reason_codes": ["STOP_VALUE_INCLUDED"],
  "reason_summary": "当前答案包含了停止值 10。",
  "mastery_effect": "no_change",
  "next_step": "阅读一级提示后重新尝试。"
}
```

`reason_summary` 是可公开的决策摘要，不是模型思维链。

### `TraceSummary`

```json
{
  "trace_id": "trace_01",
  "tool": "diagnose_misconception",
  "label": "识别错因",
  "status": "succeeded",
  "started_at": "2026-08-15T10:00:00Z",
  "duration_ms": 4
}
```

## 4. 首页

### `GET /api/v1/home`

返回当前本地体验学习者的下一步建议。

```json
{
  "learner": {
    "id": "local-learner",
    "display_name": "体验学习者",
    "provider": "local"
  },
  "recommendation": {
    "knowledge_point_id": "python.range",
    "title": "确认 range() 的停止值规则",
    "reason": "最近一次作答仍需要独立验证。",
    "action": "resume_session",
    "session_id": "session_01"
  },
  "mastery": {
    "knowledge_point_id": "python.range",
    "knowledge_point_name": "Python range()",
    "mastery_state": "learning",
    "evidence_level": "assisted",
    "reason": "使用提示后完成，尚无独立迁移证据。",
    "updated_at": "2026-08-15T10:00:00Z"
  }
}
```

没有现有会话时，`action` 为 `start_session`，`session_id` 为 `null`。最近一次迁移使用过提示、仍待独立验证时，`action` 为 `start_transfer_verification`；前端创建的新会话会直接进入无提示迁移任务。

## 5. 学习会话

### `POST /api/v1/sessions`

请求：

```json
{
  "knowledge_point_id": "python.range"
}
```

响应 `201 Created`：

```json
{
  "session_id": "session_01",
  "revision": 1,
  "session_phase": "diagnostic",
  "task": {
    "id": "range-diagnostic-01",
    "kind": "sequence_prediction",
    "prompt": "写出 list(range(2, 10, 3)) 的结果。",
    "code": "list(range(2, 10, 3))",
    "answer_format": "python_list"
  },
  "hint": null,
  "decision": {
    "action": "await_answer",
    "title": "先独立完成诊断题",
    "reason_codes": ["INITIAL_DIAGNOSTIC"],
    "reason_summary": "还没有足够证据判断当前理解。",
    "mastery_effect": "no_change",
    "next_step": "提交你认为会生成的列表。"
  },
  "mastery": {
    "knowledge_point_id": "python.range",
    "knowledge_point_name": "Python range()",
    "mastery_state": "unassessed",
    "evidence_level": "none",
    "reason": "尚无作答证据。",
    "updated_at": "2026-08-15T10:00:00Z"
  }
}
```

### `GET /api/v1/sessions/{session_id}`

恢复会话时返回与创建会话相同的主体结构，并增加：

```json
{
  "created_at": "2026-08-15T10:00:00Z",
  "updated_at": "2026-08-15T10:02:00Z",
  "attempt_count": 2,
  "highest_hint_level": 1
}
```

### `POST /api/v1/sessions/{session_id}/attempts`

请求：

```json
{
  "task_id": "range-diagnostic-01",
  "answer": "[2, 5, 8, 10]",
  "expected_revision": 1
}
```

响应 `200 OK`：

```json
{
  "attempt": {
    "id": "attempt_01",
    "normalized_answer": [2, 5, 8, 10],
    "correct": false,
    "assistance_level": 0,
    "diagnosis_code": "STOP_VALUE_INCLUDED",
    "diagnosis": "你把停止值 10 也包含进结果了。"
  },
  "session": {
    "session_id": "session_01",
    "revision": 2,
    "session_phase": "guided_practice",
    "task": {
      "id": "range-diagnostic-01",
      "kind": "sequence_prediction",
      "prompt": "写出 list(range(2, 10, 3)) 的结果。",
      "code": "list(range(2, 10, 3))",
      "answer_format": "python_list"
    },
    "hint": {
      "level": 1,
      "content": "先判断停止值本身是否会被包含。",
      "reveals_answer": false
    }
  },
  "decision": {
    "action": "retry_with_hint",
    "title": "先澄清停止值规则",
    "reason_codes": ["STOP_VALUE_INCLUDED"],
    "reason_summary": "当前答案包含了停止值 10。",
    "mastery_effect": "no_change",
    "next_step": "根据一级提示重新尝试。"
  },
  "mastery": {
    "knowledge_point_id": "python.range",
    "knowledge_point_name": "Python range()",
    "mastery_state": "learning",
    "evidence_level": "none",
    "reason": "当前作答尚未形成正确证据。",
    "updated_at": "2026-08-15T10:02:00Z"
  },
  "trace": [
    {
      "trace_id": "trace_01",
      "tool": "parse_answer",
      "label": "解析答案",
      "status": "succeeded",
      "started_at": "2026-08-15T10:02:00Z",
      "duration_ms": 2
    },
    {
      "trace_id": "trace_02",
      "tool": "diagnose_misconception",
      "label": "识别错因",
      "status": "succeeded",
      "started_at": "2026-08-15T10:02:00Z",
      "duration_ms": 1
    }
  ]
}
```

## 6. 请求提示

### `POST /api/v1/sessions/{session_id}/hints`

请求：

```json
{
  "task_id": "range-diagnostic-01",
  "expected_revision": 2
}
```

响应包含新的 `revision`、当前提示、Agent 决策和 Trace 摘要。后端负责限制最高提示级别，并保证提示内容不直接给出答案。

## 7. 掌握证据

### `GET /api/v1/knowledge-points/{knowledge_point_id}/evidence`

```json
{
  "mastery": {
    "knowledge_point_id": "python.range",
    "knowledge_point_name": "Python range()",
    "mastery_state": "pending_verification",
    "evidence_level": "assisted",
    "reason": "当前题在一级提示后完成，仍需无提示迁移验证。",
    "updated_at": "2026-08-15T10:10:00Z"
  },
  "required_next_evidence": "在不使用提示的情况下完成迁移题。",
  "items": [
    {
      "evidence_id": "evidence_01",
      "session_id": "session_01",
      "task_id": "range-diagnostic-01",
      "evidence_level": "assisted",
      "correct": true,
      "hint_level": 1,
      "summary": "使用一级提示后正确写出序列。",
      "created_at": "2026-08-15T10:10:00Z"
    }
  ]
}
```

证据列表按时间倒序返回；前端不得根据列表自行推导正式掌握状态。

## 8. Agent Trace

### `GET /api/v1/sessions/{session_id}/trace`

```json
{
  "session_id": "session_01",
  "items": [
    {
      "trace_id": "trace_02",
      "tool": "diagnose_misconception",
      "label": "识别错因",
      "status": "succeeded",
      "input_summary": "已规范化的四项整数列表",
      "output_summary": "识别为停止值包含错误",
      "error": null,
      "started_at": "2026-08-15T10:02:00Z",
      "duration_ms": 1
    }
  ]
}
```

Trace 只包含安全摘要。原始模型提示、思维链、密钥、堆栈和敏感数据不得通过 API 返回。

## 9. 错误格式

所有 API 错误使用统一结构：

```json
{
  "error": {
    "code": "INVALID_ANSWER_FORMAT",
    "message": "请输入类似 [2, 5, 8] 的整数列表。",
    "retryable": true,
    "field": "answer",
    "request_id": "req_01",
    "details": {}
  }
}
```

### v0.1 错误码

```text
INVALID_ANSWER_FORMAT     422  输入无法按当前任务格式解析
INVALID_REQUEST           422  请求字段缺失或不符合接口约束
TASK_MISMATCH             409  提交的任务不是会话当前任务
STALE_SESSION_REVISION    409  会话已被其他请求更新
SESSION_NOT_FOUND         404  会话不存在
KNOWLEDGE_POINT_NOT_FOUND 404  知识点不存在
PERSISTENCE_FAILED        503  本地持久化失败，可重试
INTERNAL_ERROR            500  未分类服务端错误
```

“证据不足”是正常领域结果，通过 `decision.mastery_effect` 和 `mastery.reason` 返回，不应作为 HTTP 错误。

## 10. 契约维护规则

- 前端根据本文档维护 TypeScript 类型和脱敏夹具。
- 后端使用 Pydantic 模型实现同一契约，并导出 OpenAPI 文档。
- OpenAPI、TypeScript 类型和本文档应保持同步。
- 契约测试至少覆盖正常作答、提示后答对、独立迁移、格式错误和版本冲突。
- 删除字段、改变字段含义或扩展枚举时，必须通过 Pull Request 记录兼容性影响。

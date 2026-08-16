# 知迭（Zhidie MasteryAgent）

[![CI](https://github.com/woshimaxfive/zhidie-mastery-agent/actions/workflows/ci.yml/badge.svg)](https://github.com/woshimaxfive/zhidie-mastery-agent/actions/workflows/ci.yml)

知迭是一个以“掌握证据”为核心的个性化学习 Agent。它根据学习者的真实作答进行诊断，选择适当的渐进引导，通过迁移任务验证独立掌握，并据此决定下一步学习动作。

v0.1 提供一条可运行的纵向切片，聚焦 Python `range()`，但产品架构不绑定单一知识点。系统默认离线运行，掌握状态由确定性领域规则更新，不需要 API Key。

## v0.1 学习闭环

跑通并验证以下真实闭环：

```text
诊断 → 引导 → 尝试 → 迁移验证 → 掌握证据更新 → 下一步决策
```

## 已实现能力

- 不同答案触发不同错因诊断；
- 根据具体错因选择三级渐进提示，提示不直接给出答案；
- 提示后答对只记录辅助证据；
- 使用会话级迁移变式，并通过实际执行结果验证等价参数；
- 只有无提示迁移成功才更新为已掌握；
- 使用 SQLite 保存会话、作答、掌握证据和 Agent Trace；
- 前端展示学习首页、任务工作台、掌握证据与执行记录；
- 包含异常输入、证据不足和会话版本冲突处理；
- 后端规则测试与完整流程测试。

## 快速启动（Windows PowerShell）

需要 Python 3.11+、Node.js 20+ 和 pnpm。

第一次使用可以先阅读[使用指南](docs/USER_GUIDE.md)，了解诊断、提示、迁移验证和掌握证据的完整操作流程。

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\start.ps1
```

脚本会建立本地 Python 虚拟环境、安装依赖并启动：

- 前端：<http://127.0.0.1:5173>
- 后端 API：<http://127.0.0.1:8000>
- OpenAPI 文档：<http://127.0.0.1:8000/docs>

在启动脚本窗口按回车会停止两个服务。本地 SQLite 数据写入 `backend/data/mastery.db`，该文件不会提交到 Git。

## 分步启动

后端：

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".\backend[dev]"
Set-Location .\backend
..\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

另开一个 PowerShell 窗口启动前端：

```powershell
Set-Location .\frontend
pnpm install --frozen-lockfile
pnpm dev
```

## 验证

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\test.ps1
```

验证脚本运行后端测试和前端生产构建。

完整浏览器闭环测试会启动隔离的前后端进程，并使用独立 SQLite 文件：

```powershell
pnpm --dir frontend exec playwright install chromium
pnpm --dir frontend test:e2e
```

## 项目文档

- 产品范围与验收标准：[产品需求](docs/PRODUCT_REQUIREMENTS.md)
- 页面与交互契约：[前端设计](docs/FRONTEND_DESIGN.md)
- 前后端数据契约：[API 契约](docs/API_CONTRACT.md)
- 贡献、审查与提交规则：[协作规范](CONTRIBUTING.md)
- 安全问题报告：[安全政策](SECURITY.md)
- 第三方依赖许可：[第三方软件声明](THIRD_PARTY_NOTICES.md)

## 仓库边界

本仓库仅包含可公开的源代码、模拟数据和工程文档，不包含未获授权的第三方材料、个人隐私、真实用户数据、数据库、`.env` 或 API Key。

## v0.1 范围

- 仅实现 Python `range()` 一个知识点；
- 使用本地体验身份，不包含登录和多用户隔离；
- 默认采用确定性离线规则，不包含在线模型服务；
- 不包含教师端、课程编辑、RAG、文件上传或真实代码沙箱。

README 和界面仅描述已经实现并经过验证的能力。

## 许可证

本项目采用 [Apache License 2.0](LICENSE)。第三方组件仍适用其各自许可证。

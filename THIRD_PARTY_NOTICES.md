# 第三方软件声明

知迭使用包管理器安装第三方开源依赖，仓库不直接收录这些依赖的源代码。各依赖仍适用其各自许可证；项目的 Apache-2.0 许可证不会替代第三方许可证。

以下版本来自当前锁文件或已验证的后端环境。完整依赖关系以 `frontend/pnpm-lock.yaml` 和 `backend/pyproject.toml` 为准。

## 前端直接依赖

| 组件 | 当前版本 | 许可证 | 项目地址 |
| --- | --- | --- | --- |
| React | 19.2.8 | MIT | <https://github.com/facebook/react> |
| React DOM | 19.2.8 | MIT | <https://github.com/facebook/react> |
| React Router DOM | 7.18.2 | MIT | <https://github.com/remix-run/react-router> |
| TypeScript | 7.0.2 | Apache-2.0 | <https://github.com/microsoft/TypeScript> |
| Vite | 8.2.1 | MIT | <https://github.com/vitejs/vite> |
| Vite React plugin | 6.0.5 | MIT | <https://github.com/vitejs/vite-plugin-react> |
| React type definitions | 19.2.18 | MIT | <https://github.com/DefinitelyTyped/DefinitelyTyped> |
| React DOM type definitions | 19.2.4 | MIT | <https://github.com/DefinitelyTyped/DefinitelyTyped> |

前端锁文件中的间接依赖还使用 MIT、Apache-2.0、BSD-3-Clause、ISC 和 MPL-2.0 许可证。构建工具链包含 MPL-2.0 的 Lightning CSS；项目没有修改或收录其源代码。

## 后端直接依赖

| 组件 | 已验证版本 | 许可证 | 项目地址 |
| --- | --- | --- | --- |
| FastAPI | 0.141.1 | MIT | <https://github.com/fastapi/fastapi> |
| Pydantic | 2.13.4 | MIT | <https://github.com/pydantic/pydantic> |
| Uvicorn | 0.52.3 | BSD-3-Clause | <https://github.com/Kludex/uvicorn> |
| HTTPX（开发） | 0.28.1 | BSD-3-Clause | <https://github.com/encode/httpx> |
| pytest（开发） | 8.4.2 | MIT | <https://github.com/pytest-dev/pytest> |

依赖版本可能在符合声明范围时更新。发布或分发构建产物前，应根据实际锁文件重新生成许可证清单并保留对应许可证文本。

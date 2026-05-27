# MVP 实施计划

## 阶段 1：基于现有目录完成项目初始化

当前项目结构以 `frontend/`、`backend/`、`docs/` 三层为准：

```text
ArcticCAD-Agent/
  frontend/    # Vue3 + Vite + shadcn-vue 工作台
  backend/     # OpenHarness 改造后的 CAD Agent 后端
  docs/        # 需求、架构、技术路线、MVP、UI 和 JSCAD skill 文档
```

- 保留已搭建的 `frontend/` Vue/Vite 项目。
- 将 OpenHarness 开源库搬入或整理为 `backend/`，作为后端 agent harness 基座。
- 文档、README 和后续任务说明均以该目录结构为准。
- 不再使用旧的 `apps/web`、`apps/api`、`packages/cad-runtime`、`packages/shared` 目录方案。

## 阶段 2：shadcn-vue 前端工作区

- 基于现有 `frontend/` 继续配置 shadcn-vue、Tailwind CSS 和 lucide-vue-next。
- 使用 Vue 3、Vite、TypeScript 和 `<script setup lang="ts">`。
- 采用 slate/neutral 色系、低圆角、轻量边框和高信息密度布局。
- 集成 Monaco Editor。
- 集成 JSCAD runtime 和 renderer。
- 前端通过 API client 与后端通信，不直接依赖 OpenHarness 内部实现。
- 前端可使用 mock API 独立开发工作台、事件流、代码编辑器和渲染反馈。

## 阶段 3：JSCAD Skill 建设

- 汇总 OpenJSCAD 官方 README、tutorials、modeling、renderer、serializer 文档。
- 建立 `jscad-authoring` skill。
- 定义 JSCAD API 白名单和标准代码模板。
- 定义禁止编造 API、禁止 DOM/网络/文件系统调用等规则。
- 建立常见错误和修复 prompt 规范。

## 阶段 4：OpenHarness 后端改造

- 将 OpenHarness 搬入或整理为 `backend/`。
- 保留核心 agent loop、tools、skills、provider、permissions、memory、stream-json 能力。
- 移除或弱化 TUI、ohmo、通用 CLI 入口，不让它们进入主业务路径。
- 包装为 CAD 专用 Orchestrator，负责绘图、改图、识图、审图和修复流程。
- 后端可在无前端情况下通过 API 测试验证 agent 流程。

## 阶段 5：接口层分离

- 前端只依赖 API client 和事件协议，不直接耦合 OpenHarness 内部模块。
- 后端按 API layer、application layer、domain layer、tool layer、provider layer 分层。
- CAD tools、model providers、knowledge providers、artifact store 均通过接口注入。
- DeepSeek、GLM、知识库、存储和导出能力都应可替换。
- JSCAD 执行错误统一通过 `JscadRunResult` 回传。

## 阶段 6：DeepSeek JSCAD 代码生成闭环

- 接入 OpenAI-compatible DeepSeek client。
- 支持用户需求生成 JSCAD。
- 将生成代码写入项目工作区，而不是只在聊天中输出。
- 前端执行并渲染 JSCAD。
- 保存代码版本和运行事件。
- 无 API key 时提供 mock 结果。

## 阶段 7：JSCAD 代码写入与错误修复闭环

- 前端截获语法错误、JSCAD API 错误、几何返回错误、渲染错误和导出错误。
- 报错信息通过统一 `JscadRunResult` 回传给智能体。
- 智能体结合原始需求、当前代码和错误日志进行最小修复。
- 修复代码写入新版本。
- 前端重新渲染验证。
- MVP 至少支持一次自动修复循环。

## 阶段 8：GLM 视觉审图闭环

- 接入 GLM 视觉 provider。
- 前端支持画布截图上传。
- 后端返回识图描述和审图建议。
- 审图结果可触发改图建议或自动修复。
- 无 API key 时提供 mock 审图结果。

## 阶段 9：导出与归档

- 前端提供 SVG/STL/DXF 导出入口。
- 后端记录导出任务。
- 保存代码版本、截图、报告和运行事件。
- 后续预留 AutoCAD/DWG 桥接。

## 验收标准

- README 与 docs 中的目录结构统一为 `frontend/`、`backend/`、`docs/`。
- 输入“生成一个适合高寒地区临建模块的 3D 草图”可得到 JSCAD 代码并写入工作区。
- 前端能渲染智能体生成的 JSCAD 代码。
- AI 生成的 JSCAD 代码不得使用未进入 skill/API 白名单的虚构接口。
- 修改需求能产生新代码版本。
- 前端必须能截获 JSCAD 执行和渲染报错。
- 报错必须能通过 `JscadRunResult` 回传给智能体进行下一轮修复。
- 至少支持一次自动修复循环。
- 修复前后代码版本都需要保留。
- 当前画布可截图并提交 GLM 审图。
- 审图报告包含问题、风险等级、修改建议和是否建议自动改图。
- AI 状态流必须展示思考、skill 加载、工具调用、写入、渲染、报错、修复和结果。
- UI 必须是紧凑式 SaaS 工作台，不做大圆角、大留白、宣传页式布局。
- 没有知识库和 AutoCAD 时系统仍可完整运行。

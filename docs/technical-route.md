# 技术路线

## 总体选择

寒地智建采用 `frontend/`、`backend/`、`docs/` 三层工程结构。`frontend/` 是 Vue/Vite/shadcn-vue 工作台，`backend/` 是基于 OpenHarness 领域化改造的 CAD Agent 后端，`docs/` 存放需求、架构、技术路线、MVP、UI 和 JSCAD skill 文档。

系统不是传统 MCP-only 架构。MCP 更适合暴露工具，而寒地智建需要完整的智能体任务编排、代码生成、工具调用、状态流、错误修复、视觉审图和项目归档能力。因此后端优先复用 OpenHarness 的 agent loop、tools、skills、memory、permissions、stream-json 事件等能力，并裁剪为 CAD 专用 harness。

## 工程目录

```text
ArcticCAD-Agent/
  frontend/    # Vue3 + Vite + shadcn-vue CAD 工作台
  backend/     # OpenHarness 改造后的 CAD Agent 后端
  docs/        # 项目文档
```

`backend/` 不是把 OpenHarness 当黑盒 CLI 调用，而是以 OpenHarness 为后端基座，封装出 CAD Orchestrator、接口层、工具层和 provider adapter。

## 前端技术

- Vue 3 + Vite + TypeScript。
- 采用 `<script setup lang="ts">`。
- shadcn-vue 作为组件库。
- Tailwind CSS 作为样式系统。
- lucide-vue-next 作为图标库。
- Pinia 管理项目状态。
- Monaco Editor 编辑 JSCAD 代码。
- `@jscad/modeling` 提供几何 API。
- `@jscad/regl-renderer` 渲染 2D/3D 几何。
- `@jscad/svg-serializer`、`@jscad/stl-serializer`、`@jscad/dxf-serializer` 提供导出。

界面遵循紧凑 SaaS 工作台风格：slate/neutral 色系，低圆角或近直角，轻量边框，高信息密度，不做营销页式首屏。

## 高内聚低耦合原则

- 前端只关心工作台状态、代码编辑、渲染结果、用户输入和 Agent 事件流。
- 前端通过 API client 调用后端，不直接依赖 OpenHarness 内部模块或 Python 包路径。
- 后端只通过接口接收前端 JSCAD 运行结果，不依赖浏览器实现细节。
- CAD Orchestrator 只编排业务流程，不直接写死 DeepSeek、GLM、文件系统或 AutoCAD 实现。
- 模型 provider 可替换，DeepSeek/GLM 通过 `ModelRouter` 接入，不写死在业务用例中。
- JSCAD skill、知识库、存储、导出、AutoCAD 桥接均通过 plugin 或 adapter 接入。
- 领域模型和事件协议保持稳定，基础设施实现可以替换。

## OpenHarness 改造策略

- 保留：engine、tools、skills、permissions、provider、memory、stream-json 事件能力。
- 弱化：TUI、ohmo、通用聊天客户端和通用 CLI 入口。
- 新增：CAD Orchestrator、JSCAD 工具、审图工具、项目归档、模型路由、前端 API。
- 隔离：OpenHarness 内部结构只在 `backend/` 内部使用，前端和领域文档只依赖公开接口。
- 扩展：后续可以将 CAD tools 暴露为 MCP 工具，但主业务链路不依赖 MCP-only 模式。

## JSCAD 的定位

JSCAD 不是单纯的渲染库，而是 MVP 的核心图纸表达语言。智能体通过生成和修改 JavaScript/JSCAD 代码来完成绘图与改图，再由前端执行并渲染结果。

这一路线的好处是：

- JavaScript 对大模型更友好，代码生成和修复能力强于 AutoLISP。
- JSCAD 可在浏览器运行，用户无需安装 CAD 软件即可预览 2D/3D 图纸。
- 代码天然可版本化、可审查、可 diff、可回放。
- 后续可通过导出 DXF/STL/SVG 和 AutoCAD 桥接进入传统 CAD 工具链。

## JSCAD 代码生成与修复闭环

1. 用户提出绘图或改图需求。
2. CAD Orchestrator 加载 JSCAD skill 和项目上下文。
3. DeepSeek 生成或修改 JSCAD 代码。
4. 系统写入当前项目版本，如 `main.js`。
5. 前端执行 JSCAD 并渲染结果。
6. 前端截获语法错误、运行错误、JSCAD API 错误、几何返回错误、渲染错误和导出错误。
7. 错误日志通过 `JscadRunResult` 和事件流回传智能体。
8. 智能体结合用户需求、当前代码和错误信息进行最小修复。
9. 修复版本再次写入、执行、渲染和归档。

## JSCAD Skill 约束

为降低 AI 编造接口的概率，必须建立 `jscad-authoring` skill。智能体生成 JSCAD 前需要加载该 skill，并遵循 API 白名单和代码模板。

skill 来源包括：

- `OpenJSCAD.org/README.md`
- `OpenJSCAD.org/jsdoc/tutorials/*.md`
- `OpenJSCAD.org/packages/modeling/README.md`
- `OpenJSCAD.org/packages/utils/regl-renderer/README.md`
- `OpenJSCAD.org/packages/io/*-serializer/README.md`

生成约束：

- 必须导出 `main`。
- `main()` 必须返回 JSCAD geometry 或 geometry 数组。
- 不允许调用未进入 skill/API 白名单的接口。
- 不允许使用浏览器 DOM、网络请求或文件系统。
- 建筑构件应拆成具名函数。
- 参数集中定义，便于后续 UI 参数化。

## 后端技术

后端基于 OpenHarness 改造为 CAD 专用 harness：

- API layer：HTTP/SSE/WebSocket DTO 与鉴权。
- Application layer：CAD Orchestrator、任务编排、用例服务。
- Domain layer：Project、CodeVersion、AgentEvent、ReviewReport、JscadRunResult 等核心模型。
- Tool layer：JSCAD 写入、审图、导出、截图、AutoCAD 桥接工具。
- Provider layer：DeepSeek、GLM、Knowledge、Storage、CAD Export adapter。

## 模型路由

- DeepSeek：主对话、需求理解、JSCAD 代码生成、代码修复。
- GLM Vision：图像理解、截图识别、视觉审图。
- Knowledge Provider：独立接口，MVP 默认返回空结果。

MVP 采用单主 Agent + 多模型路由。后续可拆分 Designer、Reviewer、Vision、Export 多 Agent。

## AutoCAD 兼容

MVP 不依赖 AutoCAD。后续从 CADx 迁移 COM/mock 后端能力：

- 打开 DXF 到 AutoCAD。
- 转换为 DWG。
- 导出 CAD 截图。
- 提取 CAD 实体信息。

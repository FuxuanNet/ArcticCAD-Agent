# 寒地智建

寒地智建：面向高寒地区建筑图纸生成与审核的智能体平台。

工程代号：ArcticCAD-Agent。

项目目标是形成一条快速闭环：

1. 用户提出绘图、改图、识图或审图需求。
2. CAD Orchestrator 生成或修改 JSCAD 代码。
3. 前端工作台写入并渲染 2D/3D 图纸。
4. 前端截获 JSCAD 执行和渲染错误。
5. 智能体根据错误进行下一轮修复。
6. 系统可用 GLM 视觉模型对截图进行识图和审图。

## Layout

```text
frontend/  Vue3 + Vite + shadcn-vue CAD 工作台
backend/   OpenHarness 改造后的 CAD Agent 后端
docs/      需求、架构、技术路线、MVP、UI 和 JSCAD skill 文档
```

`backend/` 规划承载 OpenHarness 的领域化改造代码。OpenHarness 作为后端 agent harness 基座使用，业务接口需要再封装，避免前端或领域逻辑直接耦合 OpenHarness 内部模块。

## Project Skills

ArcticCAD 项目级 skill 统一放在根目录 `.agents/skills/<skill-name>/SKILL.md`。
当前保留的业务 skill 是 `.agents/skills/jscad-authoring/SKILL.md`，供后端通过 OpenHarness loader 从项目根目录加载。
不要在 `backend/.agents` 或 `backend/.claude` 下放置 ArcticCAD 业务 skill。

## Development

前端：

```bash
cd frontend
npm run dev
```

后端：

```bash
cd backend
uv sync
uv run uvicorn <backend_api_entry>:app --reload --host 127.0.0.1 --port 8765
```

后端入口名称以后端实际整理结果为准。没有真实模型 API key 时，建议保留 mock provider，确保前端工作台和 agent 事件流可独立开发。

## Documentation

- `docs/requirements.md`：功能需求与研究目的。
- `docs/technical-route.md`：技术路线与 OpenHarness 改造策略。
- `docs/architecture.md`：系统架构、接口分层和事件协议。
- `docs/mvp-plan.md`：MVP 阶段与验收标准。
- `docs/jscad-skill-strategy.md`：JSCAD skill 与 API 白名单策略。
- `docs/ui-design-spec.md`：shadcn-vue 工作台 UI 规范。

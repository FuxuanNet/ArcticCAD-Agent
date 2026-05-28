# UI 设计规范

## 产品名称

主标题：高寒智建

副标题：面向高寒地区建筑图纸生成与审核的智能体平台

工程代号：ArcticCAD-Agent

## 技术要求

- Vue 3 + Vite + TypeScript。
- 组件使用 shadcn-vue。
- Vue 组件使用 `<script setup lang="ts">`。
- 样式使用 Tailwind CSS 语义 token。
- 图标使用 lucide-vue-next。
- 遵循 `docs/组件库.md` 的 shadcn-vue 安装配置。

## 视觉风格

- 紧凑式 SaaS 工作台。
- slate/neutral 色系为主。
- 低圆角或近直角，建议圆角控制在 2px-6px。
- 轻量边框、低对比阴影、高信息密度。
- 首屏就是可操作工作区，不做营销页或大幅 hero。
- 图纸区域优先，聊天区和报告区服务于工作流，不喧宾夺主。
- 避免大圆角、大留白、渐变背景、装饰性卡片堆叠。

## 推荐组件

- `Sidebar`：项目、版本、导出和资源导航。
- `Resizable`：画布、代码区、对话区可调整布局。
- `Tabs`：代码、参数、审图报告、运行日志切换。
- `ScrollArea`：聊天记录、事件流、工具日志。
- `Button`：主要操作，使用 lucide 图标并遵循 shadcn-vue 图标规则。
- `Badge`：模型、状态、风险等级、版本号。
- `Progress`：工具执行和修复进度。
- `Tooltip`：图标按钮说明。
- `Sheet`：AI 对话或详细审图报告抽屉。
- `Command`：命令面板。
- `Separator`：区域分隔。
- `Textarea`：用户输入。
- `DropdownMenu`：导出、版本、模型选择。
- `Alert`：渲染错误、审图风险和系统提示。

## 工作台布局

- 左侧窄栏：项目列表、版本历史、导出入口。
- 顶部工具栏：项目名、当前版本、模型状态、保存/导出/审图按钮。
- 中央主区：JSCAD 2D/3D 画布。
- 右侧面板：Monaco 代码编辑器、参数、审图报告 Tabs。
- 底部或右下抽屉：AI 对话、事件流、工具调用日志。

所有固定格式 UI 元素需要稳定尺寸，避免工具栏、按钮、状态标签因文本变化导致布局跳动。

## AI 状态输出

AI 对话区不仅展示最终回答，还必须展示任务过程：

- 正在思考。
- 正在加载 JSCAD skill。
- 正在调用工具。
- 正在写入代码。
- 正在渲染。
- 渲染失败与错误摘要。
- 正在修复。
- 修复完成。
- GLM 正在识图或审图。
- 工具调用结果。
- 任务完成或失败。

思考内容只展示可公开的摘要，不展示完整链式推理。

## Agent 事件展示

事件流按时间线展示，建议分为四类：

- 模型事件：thinking、skill_loading、vision_review。
- 工具事件：tool_start、tool_progress、tool_result。
- 代码事件：code_patch、code_write_start、code_write_done、render_request。
- 修复事件：render_error、repair_start、repair_done、error、done。

每条事件至少展示状态、时间、简短说明。工具事件需要展示工具名、输入摘要、进度和结果摘要。

## shadcn-vue 使用规则

- 优先使用已有组件，不手写可替代的自定义组件。
- 使用语义颜色，如 `bg-background`、`text-muted-foreground`、`border-border`。
- 使用 `gap-*` 组织间距，不使用 `space-x-*` 或 `space-y-*`。
- 图标放在 `Button` 中时使用 `data-icon`。
- 表单布局使用 `FieldGroup` 和 `Field`。
- 状态标签使用 `Badge`，不要手写彩色 `span`。
- 错误提示使用 `Alert`。
- 加载态使用 `Skeleton` 或 `Spinner`。

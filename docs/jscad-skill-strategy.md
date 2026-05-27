# JSCAD Skill 策略

## 目的

JSCAD 是寒地智建 MVP 的核心图纸表达语言。为了避免智能体凭记忆编造不存在的 API，必须建立 `jscad-authoring` skill，让智能体在生成、修改和修复代码前读取稳定的 JSCAD 写作规范。

该 skill 的目标是：

- 提高 JSCAD 代码一次执行成功率。
- 约束 AI 只使用官方 API 和项目白名单 API。
- 为错误修复提供可重复的诊断路径。
- 让图纸代码具备可读、可版本化、可参数化的工程结构。

## 来源材料

skill 内容从以下本地官方资料整理：

- `OpenJSCAD.org/README.md`
- `OpenJSCAD.org/jsdoc/tutorials/01_gettingStarted.md`
- `OpenJSCAD.org/jsdoc/tutorials/02_modelingBasics.md`
- `OpenJSCAD.org/jsdoc/tutorials/03_usingParameters.md`
- `OpenJSCAD.org/jsdoc/tutorials/04_multifileProjects.md`
- `OpenJSCAD.org/jsdoc/tutorials/05_importingFiles.md`
- `OpenJSCAD.org/packages/modeling/README.md`
- `OpenJSCAD.org/packages/utils/regl-renderer/README.md`
- `OpenJSCAD.org/packages/io/dxf-serializer/README.md`
- `OpenJSCAD.org/packages/io/svg-serializer/README.md`
- `OpenJSCAD.org/packages/io/stl-serializer/README.md`

## 标准代码模板

```js
const { cuboid, cylinder } = require('@jscad/modeling').primitives
const { translate } = require('@jscad/modeling').transforms
const { union } = require('@jscad/modeling').booleans

const main = () => {
  const base = cuboid({ size: [12000, 6000, 300] })
  const wall = translate([0, 0, 1800], cuboid({ size: [12000, 200, 3600] }))
  return union(base, wall)
}

module.exports = { main }
```

## 生成规则

- 必须导出 `main`。
- `main()` 必须返回 JSCAD geometry 或 geometry 数组。
- 不允许调用未在 skill/API 白名单中的接口。
- 不允许使用浏览器 DOM、网络请求、文件系统或动态远程加载。
- 所有建筑构件应拆成具名函数，例如 `createFoundation()`、`createInsulationLayer()`、`createWindBrace()`。
- 参数集中定义，便于后续前端参数化和审图。
- 单位默认使用毫米，并在代码注释中说明关键尺寸含义。
- 生成失败时必须根据错误信息最小修改，不整段重写无关代码。

## API 白名单方向

首批白名单聚焦稳定、常用、适合建筑构件表达的 API：

- primitives：`cuboid`、`cube`、`cylinder`、`sphere`、`circle`、`rectangle`、`polygon`、`line`。
- transforms：`translate`、`rotateX`、`rotateY`、`rotateZ`、`scale`、`mirror`。
- booleans：`union`、`subtract`、`intersect`。
- extrusions：`extrudeLinear`、`extrudeRotate`。
- colors：`colorize`。
- measurements：用于后续几何校验和审图摘要。

新增 API 必须先进入 skill 文档和测试样例，再允许智能体使用。

## 错误修复规则

智能体收到错误后，应按以下顺序处理：

1. 判断错误类型：语法、API、geometry、render、export。
2. 定位错误行号或相关函数。
3. 保留与错误无关的代码和尺寸参数。
4. 优先替换不存在的 API、修复 import、修复 `main()` 返回值。
5. 生成新版本，并说明修复点。
6. 请求前端重新渲染验证。

## 禁止项

- 禁止输出只有说明没有代码的“伪绘图结果”。
- 禁止使用未确认存在的 OpenJSCAD/JSCAD API。
- 禁止把 Three.js、Canvas、DOM API 混入 JSCAD 代码。
- 禁止在 JSCAD 代码中访问网络、读写本地文件或读取环境变量。
- 禁止在修复小错误时大规模重写用户已有结构。

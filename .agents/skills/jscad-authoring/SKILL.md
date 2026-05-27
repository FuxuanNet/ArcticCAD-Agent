---
name: jscad-authoring
description: Write, modify, and repair safe JSCAD code for ArcticCAD building sketches.
---

# JSCAD Authoring

Use this skill before generating or repairing JSCAD code for ArcticCAD projects.

## Required Shape

```js
const { cuboid, cylinder } = require('@jscad/modeling').primitives
const { translate } = require('@jscad/modeling').transforms
const { union } = require('@jscad/modeling').booleans

const params = {
  length: 12000,
  width: 6000,
  height: 3600,
}

function createFoundation() {
  return cuboid({ size: [params.length, params.width, 300] })
}

function main() {
  return union(createFoundation())
}

module.exports = { main }
```

## Rules

- Export `main` with `module.exports = { main }`.
- `main()` must return a JSCAD geometry or geometry array.
- Keep dimensions in millimeters unless the user says otherwise.
- Put project parameters in one `params` object.
- Split building elements into named functions.
- Use only stable JSCAD APIs from this whitelist:
  - primitives: `cuboid`, `cube`, `cylinder`, `sphere`, `circle`, `rectangle`, `polygon`, `line`
  - transforms: `translate`, `rotateX`, `rotateY`, `rotateZ`, `scale`, `mirror`
  - booleans: `union`, `subtract`, `intersect`
  - extrusions: `extrudeLinear`, `extrudeRotate`
  - colors: `colorize`
- Do not use DOM, browser APIs, network calls, local file system access, remote imports, or environment variables.
- When repairing errors, make the smallest change that fixes the reported syntax/API/geometry/render/export issue.

const fs = require('fs')

function boundsFromPoints(points) {
  if (!points.length) return null
  const dimensions = Math.max(...points.map((point) => point.length))
  const min = Array.from({ length: dimensions }, () => Number.POSITIVE_INFINITY)
  const max = Array.from({ length: dimensions }, () => Number.NEGATIVE_INFINITY)
  for (const point of points) {
    for (let i = 0; i < dimensions; i++) {
      const value = Number(point[i] || 0)
      min[i] = Math.min(min[i], value)
      max[i] = Math.max(max[i], value)
    }
  }
  return { min, max }
}

function collectGeometryPoints(value, points = []) {
  if (Array.isArray(value)) {
    for (const item of value) collectGeometryPoints(item, points)
    return points
  }
  if (!value || typeof value !== 'object') return points
  if (Array.isArray(value.points)) {
    for (const point of value.points) {
      if (Array.isArray(point)) points.push(point.map(Number))
    }
  }
  if (Array.isArray(value.polygons)) {
    for (const polygon of value.polygons) {
      const vertices = polygon.vertices || polygon.points || polygon
      if (Array.isArray(vertices)) {
        for (const point of vertices) {
          if (Array.isArray(point)) points.push(point.map(Number))
        }
      }
    }
  }
  if (Array.isArray(value.sides)) {
    for (const side of value.sides) collectGeometryPoints(side, points)
  }
  return points
}

function countSolids(value) {
  if (Array.isArray(value)) return value.reduce((sum, item) => sum + countSolids(item), 0)
  return value ? 1 : 0
}

function run() {
  const [, , format, filePath, rawScriptPath] = process.argv
  const input = fs.readFileSync(filePath)
  if (format === 'dxf') {
    const { deserialize } = require('@jscad/dxf-deserializer')
    const source = input.toString('utf8')
    const rawScript = deserialize({ filename: filePath, output: 'script', strict: true }, source)
    fs.writeFileSync(rawScriptPath, rawScript, 'utf8')
    const geometry = deserialize({ filename: filePath, output: 'geometry', strict: true }, source)
    const points = collectGeometryPoints(geometry)
    return {
      rawScript,
      summary: {
        format: 'dxf',
        units: 'millimeters',
        bounds: boundsFromPoints(points),
        layers: [],
        entityCounts: {},
        entities: [],
        closedProfiles: [],
        warnings: [],
        rawScriptPath: null,
      },
    }
  }
  if (format === 'stl') {
    const { deserialize } = require('@jscad/stl-deserializer')
    const geometry = deserialize({ filename: filePath, output: 'geometry', addMetaData: false }, input)
    const points = collectGeometryPoints(geometry)
    return {
      rawScript: null,
      summary: {
        format: 'stl',
        bounds: boundsFromPoints(points),
        layers: [],
        entityCounts: {},
        entities: [],
        closedProfiles: [],
        triangleCount: Math.max(0, Math.floor(points.length / 3)),
        solidCount: countSolids(geometry),
        isLikelyWatertight: null,
        warnings: ['STL 已作为网格参考解析；不会自动展开为主 JSCAD polyhedron 代码。'],
      },
    }
  }
  throw new Error(`Unsupported format: ${format}`)
}

try {
  process.stdout.write(JSON.stringify(run()))
} catch (error) {
  process.stderr.write(error instanceof Error ? error.stack || error.message : String(error))
  process.exit(1)
}

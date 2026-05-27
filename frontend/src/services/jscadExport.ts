import type { JscadGeometry } from "@/services/jscadRunner"

export type ExportFormat = "svg" | "stl" | "dxf"

function downloadBlob(data: BlobPart, filename: string, type: string) {
  const blob = data instanceof Blob ? data : new Blob([data], { type })
  const url = URL.createObjectURL(blob)
  const link = document.createElement("a")
  link.href = url
  link.download = filename
  document.body.appendChild(link)
  link.click()
  link.remove()
  URL.revokeObjectURL(url)
}

function firstSerializedPart(value: unknown): BlobPart {
  const parts = Array.isArray(value) ? value : [value]
  const first = parts[0]
  if (first instanceof ArrayBuffer || ArrayBuffer.isView(first) || first instanceof Blob || typeof first === "string") {
    return first as BlobPart
  }
  return String(first ?? "")
}

export async function exportStl(geometry: JscadGeometry, filename: string) {
  const { serialize } = await import("@jscad/stl-serializer")
  const data = serialize({ binary: false }, geometry)
  downloadBlob(firstSerializedPart(data), filename, "model/stl")
}

export async function exportDxf(geometry: JscadGeometry, filename: string) {
  const { serialize } = await import("@jscad/dxf-serializer")
  const data = serialize({ geom3To: "3dface" }, geometry)
  downloadBlob(firstSerializedPart(data), filename, "application/dxf")
}

export function exportSnapshotSvg(snapshotBase64: string, filename: string) {
  if (!snapshotBase64) {
    throw new Error("当前画布还没有可导出的截图。")
  }
  const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="1280" height="720" viewBox="0 0 1280 720">
  <image href="${snapshotBase64}" width="1280" height="720" preserveAspectRatio="xMidYMid meet"/>
</svg>
`
  downloadBlob(svg, filename, "image/svg+xml")
}

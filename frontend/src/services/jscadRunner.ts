import * as jscadModeling from "@jscad/modeling"
import type { JscadRunResult } from "@/types/domain"

export type JscadGeometry = unknown
export type LocalJscadRunResult = Omit<JscadRunResult, "projectId" | "conversationId" | "autoRepairAttempt"> & {
  geometry?: JscadGeometry
}

interface ModuleLike {
  exports: Record<string, unknown>
}

function classifyError(error: unknown): LocalJscadRunResult["error"] {
  const item = error instanceof Error ? error : new Error(String(error))
  const message = item.message || "Unknown JSCAD error"
  const syntaxHints = ["Unexpected token", "Unexpected end", "missing", "Invalid or unexpected token"]
  const apiHints = ["is not a function", "Cannot read properties", "undefined"]
  const kind = syntaxHints.some((hint) => message.includes(hint))
    ? "syntax"
    : apiHints.some((hint) => message.includes(hint))
      ? "api"
      : "render"

  return {
    kind,
    message,
    stack: item.stack,
  }
}

function summarizeGeometry(value: unknown): string {
  if (Array.isArray(value)) {
    return `${value.length} geometry item${value.length === 1 ? "" : "s"} returned`
  }
  if (value && typeof value === "object") {
    const type = "geomType" in value ? String((value as { geomType?: unknown }).geomType) : "geometry"
    return `${type} returned`
  }
  return "geometry returned"
}

function isLikelyGeometry(value: unknown): boolean {
  if (Array.isArray(value)) {
    return value.length > 0 && value.every(isLikelyGeometry)
  }
  return Boolean(value && typeof value === "object")
}

export async function runJscadCode(code: string, versionId: string): Promise<LocalJscadRunResult> {
  try {
    const module: ModuleLike = { exports: {} }
    const require = (name: string) => {
      if (name === "@jscad/modeling") {
        return jscadModeling
      }
      throw new Error(`Unsupported JSCAD import: ${name}`)
    }
    const execute = new Function("module", "exports", "require", code)
    execute(module, module.exports, require)
    const main = module.exports.main

    if (typeof main !== "function") {
      return {
        ok: false,
        versionId,
        error: {
          kind: "geometry",
          message: "JSCAD code must export a main() function.",
        },
      }
    }

    const geometry = main()
    if (!isLikelyGeometry(geometry)) {
      return {
        ok: false,
        versionId,
        error: {
          kind: "geometry",
          message: "main() did not return a JSCAD geometry or geometry array.",
        },
      }
    }

    return {
      ok: true,
      versionId,
      geometrySummary: summarizeGeometry(geometry),
      geometry,
    }
  } catch (error) {
    return {
      ok: false,
      versionId,
      error: classifyError(error),
    }
  }
}

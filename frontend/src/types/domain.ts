export type AgentEventType =
  | "thinking"
  | "agent_plan"
  | "skill_loading"
  | "tool_start"
  | "tool_progress"
  | "tool_result"
  | "code_patch"
  | "code_write_start"
  | "code_write_done"
  | "render_request"
  | "render_error"
  | "repair_start"
  | "repair_done"
  | "repair_decision"
  | "user_action_required"
  | "repair_stopped"
  | "vision_review"
  | "provider_status"
  | "model_error"
  | "assistant_message"
  | "done"
  | "error"

export type JscadErrorKind = "syntax" | "api" | "geometry" | "render" | "export"

export interface Project {
  id: string
  name: string
  description: string
  region: string
  status: "active" | "archived"
  updatedAt: string
  currentVersionId: string
  currentConversationId: string
}

export interface CodeVersion {
  id: string
  projectId: string
  label: string
  summary: string
  code: string
  createdAt: string
  status: "draft" | "rendered" | "error" | "reviewed"
}

export interface AssetEntitySummary {
  id: string
  type: string
  layer?: string | null
  points?: number[][]
  center?: number[] | null
  radius?: number | null
  startAngle?: number | null
  endAngle?: number | null
  closed?: boolean
  bounds?: { min: number[]; max: number[] } | null
}

export interface AssetSummary {
  format: "dxf" | "stl"
  units?: string | null
  bounds?: { min: number[]; max: number[] } | null
  layers: string[]
  entityCounts: Record<string, number>
  entities: AssetEntitySummary[]
  closedProfiles: Record<string, unknown>[]
  triangleCount?: number | null
  solidCount?: number | null
  isLikelyWatertight?: boolean | null
  warnings: string[]
  rawScriptPath?: string | null
}

export interface CadAsset {
  id: string
  projectId: string
  filename: string
  format: "dxf" | "stl"
  status: "uploaded" | "parsed" | "parse_error"
  byteSize: number
  originalPath: string
  summaryPath?: string | null
  rawScriptPath?: string | null
  createdAt: string
  updatedAt: string
  error?: string | null
}

export interface AssetDetail {
  asset: CadAsset
  summary?: AssetSummary | null
}

export interface AssetUploadResult extends AssetDetail {}

export interface AssetRebuildRequest {
  projectId: string
  assetId: string
  prompt: string
  mode?: "reference_rebuild" | "direct_insert"
  currentVersionId?: string
  conversationId?: string
}

export interface Conversation {
  id: string
  projectId: string
  title: string
  messageCount: number
  updatedAt: string
}

export interface ChatMessage {
  id: string
  conversationId: string
  role: "user" | "assistant" | "system"
  content: string
  createdAt: string
}

export interface ReviewRisk {
  level: "low" | "medium" | "high"
  category: string
  description: string
  suggestion: string
}

export interface ReviewReport {
  summary: string
  risks: ReviewRisk[]
  drawingUnderstanding: string
  requirementMatch?: string
  codeDesignBugs?: string[]
  coldRegionNotes: string[]
  recommendAutoFix: boolean
  observations?: string[]
  suggestedFixes?: string[]
  evidence?: string[]
}

export interface ConfigStatus {
  llm: {
    provider: string
    baseUrl: string
    model: string
    status: "configured" | "missing" | string
  }
  vision: {
    provider: string
    baseUrl: string
    model: string
    status: "configured" | "missing" | string
  }
  projectsDir: string
  llmTimeoutSeconds: number
  visionTimeoutSeconds?: number
}

export interface RunRecord extends JscadRunResult {
  createdAt: string
}

export interface SnapshotArtifact {
  id: string
  projectId: string
  versionId: string
  conversationId?: string
  imageBase64?: string | null
  filename?: string
  mimeType?: string
  byteSize?: number
  source: string
  camera?: Record<string, unknown> | null
  note?: string | null
  createdAt: string
}

export interface SnapshotCleanupResult {
  ok: boolean
  deleted?: number
}

export interface SaveSnapshotInput {
  versionId: string
  conversationId?: string
  imageBase64: string
  source: string
  camera?: Record<string, unknown>
  note?: string
}

export interface AgentEventBase {
  id: string
  type: AgentEventType
  message?: string
  createdAt: string
}

export type AgentEvent =
  | (AgentEventBase & { type: "thinking"; message: string })
  | (AgentEventBase & { type: "agent_plan"; intent: "chat" | "generate" | "modify" | "review" | "ask_clarifying_question" | "run_or_repair"; confidence?: number; provider?: string; error?: string })
  | (AgentEventBase & { type: "skill_loading"; skill: string; status: "start" | "done" | "error" })
  | (AgentEventBase & { type: "tool_start"; tool: string; inputSummary: string })
  | (AgentEventBase & { type: "tool_progress"; tool: string; progress: number; message: string })
  | (AgentEventBase & { type: "tool_result"; tool: string; ok: boolean; resultSummary: string })
  | (AgentEventBase & { type: "code_patch"; language: "jscad"; code: string; summary: string })
  | (AgentEventBase & { type: "code_write_start"; target: string })
  | (AgentEventBase & { type: "code_write_done"; target: string; versionId: string })
  | (AgentEventBase & { type: "render_request"; reason: string })
  | (AgentEventBase & { type: "render_error"; errorKind: JscadErrorKind; message: string; stack?: string })
  | (AgentEventBase & { type: "repair_start"; reason: string })
  | (AgentEventBase & { type: "repair_done"; versionId: string; summary: string })
  | (AgentEventBase & { type: "repair_decision"; decision: "continue" | "stop_repair" | "needs_user_input"; reason: string })
  | (AgentEventBase & { type: "user_action_required"; message: string; reason: string })
  | (AgentEventBase & { type: "repair_stopped"; reason: string })
  | (AgentEventBase & { type: "vision_review"; provider: string; report: ReviewReport })
  | (AgentEventBase & { type: "provider_status"; provider: string; ok?: boolean; message?: string; error?: string })
  | (AgentEventBase & { type: "model_error"; provider?: string; message: string; error?: string; recoverable: boolean })
  | (AgentEventBase & { type: "assistant_message"; message: string; assistantMessage: string })
  | (AgentEventBase & { type: "done"; summary: string })
  | (AgentEventBase & { type: "error"; message: string; recoverable: boolean })

export interface JscadRunResult {
  ok: boolean
  versionId: string
  projectId: string
  conversationId: string
  autoRepairAttempt: number
  geometrySummary?: string
  error?: {
    kind: JscadErrorKind
    message: string
    stack?: string
    line?: number
    column?: number
  }
}

export interface ChatRequest {
  projectId: string
  conversationId: string
  message: string
  currentVersionId?: string
  viewportSnapshotId?: string
}

export interface ReviewRequest {
  projectId: string
  versionId: string
  conversationId?: string
  snapshotId?: string
  snapshotBase64?: string
  reviewMode?: "review" | "observe_for_change"
  userRequirement?: string
}

export interface CreateProjectInput {
  name: string
  description?: string
  region?: string
}

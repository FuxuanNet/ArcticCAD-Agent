import type {
  AgentEvent,
  AssetDetail,
  AssetRebuildRequest,
  AssetUploadResult,
  CadAsset,
  ChatMessage,
  ChatRequest,
  CodeVersion,
  ConfigStatus,
  Conversation,
  CreateProjectInput,
  JscadRunResult,
  Project,
  ReviewRequest,
  RunRecord,
  SaveSnapshotInput,
  SnapshotCleanupResult,
  SnapshotArtifact,
} from "@/types/domain"

export interface AgentGateway {
  sendMessage(input: ChatRequest, options?: { signal?: AbortSignal }): AsyncIterable<AgentEvent>
  submitRenderResult(result: JscadRunResult): AsyncIterable<AgentEvent>
  requestReview(input: ReviewRequest, options?: { signal?: AbortSignal }): AsyncIterable<AgentEvent>
  reconstructFromAsset(input: AssetRebuildRequest, options?: { signal?: AbortSignal }): AsyncIterable<AgentEvent>
}

export interface ProjectGateway {
  listProjects(): Promise<Project[]>
  createProject(input: CreateProjectInput): Promise<Project>
  getProject(projectId: string): Promise<Project>
  listVersions(projectId: string): Promise<CodeVersion[]>
  listConversations(projectId: string): Promise<Conversation[]>
  createConversation(projectId: string, title?: string): Promise<Conversation>
  listMessages(conversationId: string): Promise<ChatMessage[]>
  listRuns(projectId: string): Promise<RunRecord[]>
  saveSnapshot(projectId: string, input: SaveSnapshotInput): Promise<SnapshotArtifact>
  getSnapshot(projectId: string, snapshotId: string): Promise<SnapshotArtifact>
  listSnapshots(projectId: string): Promise<SnapshotArtifact[]>
  deleteSnapshot(projectId: string, snapshotId: string): Promise<SnapshotCleanupResult>
  deleteReviewSnapshots(projectId: string): Promise<SnapshotCleanupResult>
  uploadAsset(projectId: string, file: File): Promise<AssetUploadResult>
  listAssets(projectId: string): Promise<CadAsset[]>
  getAsset(projectId: string, assetId: string): Promise<AssetDetail>
  getConfigStatus(): Promise<ConfigStatus>
}

export interface ApiGateway {
  agent: AgentGateway
  projects: ProjectGateway
}

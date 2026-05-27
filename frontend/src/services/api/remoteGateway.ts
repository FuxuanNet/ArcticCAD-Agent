import type {
  AgentEvent,
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
  SnapshotArtifact,
} from "@/types/domain"
import type { AgentGateway, ApiGateway, ProjectGateway } from "./contracts"

const baseUrl = (import.meta.env.VITE_API_BASE_URL || "").replace(/\/+$/, "")

function url(path: string) {
  return `${baseUrl}${path.startsWith("/") ? path : `/${path}`}`
}

async function parseError(response: Response): Promise<Error> {
  const text = await response.text()
  try {
    const data = JSON.parse(text) as { detail?: unknown; message?: unknown }
    const detail = data.detail || data.message || text
    return new Error(typeof detail === "string" ? detail : JSON.stringify(detail))
  } catch {
    return new Error(text || `${response.status} ${response.statusText}`)
  }
}

async function requestJson<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(url(path), {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers || {}),
    },
  })
  if (!response.ok) {
    throw await parseError(response)
  }
  return (await response.json()) as T
}

async function* postSse<T>(path: string, body: T, options?: { signal?: AbortSignal }): AsyncIterable<AgentEvent> {
  const response = await fetch(url(path), {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Accept: "text/event-stream",
    },
    body: JSON.stringify(body),
    signal: options?.signal,
  })
  if (!response.ok) {
    throw await parseError(response)
  }
  if (!response.body) {
    return
  }

  const reader = response.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ""

  while (true) {
    const { value, done } = await reader.read()
    buffer += decoder.decode(value, { stream: !done })
    const chunks = buffer.split(/\r?\n\r?\n/)
    buffer = chunks.pop() || ""

    for (const chunk of chunks) {
      const data = chunk
        .split(/\r?\n/)
        .filter((line) => line.startsWith("data:"))
        .map((line) => line.slice(5).trimStart())
        .join("\n")
      if (data) {
        yield JSON.parse(data) as AgentEvent
      }
    }

    if (done) {
      break
    }
  }

  const trailing = buffer.trim()
  if (trailing.startsWith("data:")) {
    yield JSON.parse(trailing.slice(5).trimStart()) as AgentEvent
  }
}

class RemoteProjectGateway implements ProjectGateway {
  listProjects() {
    return requestJson<Project[]>("/api/projects")
  }

  createProject(input: CreateProjectInput) {
    return requestJson<Project>("/api/projects", {
      method: "POST",
      body: JSON.stringify(input),
    })
  }

  getProject(projectId: string) {
    return requestJson<Project>(`/api/projects/${encodeURIComponent(projectId)}`)
  }

  listVersions(projectId: string) {
    return requestJson<CodeVersion[]>(`/api/projects/${encodeURIComponent(projectId)}/versions`)
  }

  listConversations(projectId: string) {
    return requestJson<Conversation[]>(`/api/projects/${encodeURIComponent(projectId)}/conversations`)
  }

  createConversation(projectId: string, title?: string) {
    return requestJson<Conversation>(`/api/projects/${encodeURIComponent(projectId)}/conversations`, {
      method: "POST",
      body: JSON.stringify({ title }),
    })
  }

  listMessages(conversationId: string) {
    return requestJson<ChatMessage[]>(`/api/conversations/${encodeURIComponent(conversationId)}/messages`)
  }

  listRuns(projectId: string) {
    return requestJson<RunRecord[]>(`/api/projects/${encodeURIComponent(projectId)}/runs`)
  }

  saveSnapshot(projectId: string, input: SaveSnapshotInput) {
    return requestJson<SnapshotArtifact>(`/api/projects/${encodeURIComponent(projectId)}/snapshots`, {
      method: "POST",
      body: JSON.stringify(input),
    })
  }

  getSnapshot(projectId: string, snapshotId: string) {
    return requestJson<SnapshotArtifact>(
      `/api/projects/${encodeURIComponent(projectId)}/snapshots/${encodeURIComponent(snapshotId)}`,
    )
  }

  listSnapshots(projectId: string) {
    return requestJson<SnapshotArtifact[]>(`/api/projects/${encodeURIComponent(projectId)}/snapshots`)
  }

  getConfigStatus() {
    return requestJson<ConfigStatus>("/api/config/status")
  }
}

class RemoteAgentGateway implements AgentGateway {
  sendMessage(input: ChatRequest, options?: { signal?: AbortSignal }) {
    return postSse("/api/agent/chat", input, options)
  }

  submitRenderResult(result: JscadRunResult) {
    return postSse("/api/agent/render-result", result)
  }

  requestReview(input: ReviewRequest, options?: { signal?: AbortSignal }) {
    return postSse("/api/agent/review", input, options)
  }
}

export const remoteGateway: ApiGateway = {
  agent: new RemoteAgentGateway(),
  projects: new RemoteProjectGateway(),
}

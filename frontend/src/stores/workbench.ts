import { defineStore } from "pinia"
import { computed, ref } from "vue"
import { apiGateway } from "@/services/api"
import { exportDxf, exportSnapshotSvg, exportStl, type ExportFormat } from "@/services/jscadExport"
import { runJscadCode, type JscadGeometry } from "@/services/jscadRunner"
import type {
  AgentEvent,
  ChatMessage,
  CodeVersion,
  ConfigStatus,
  Conversation,
  JscadRunResult,
  Project,
  ReviewReport,
  RunRecord,
  SnapshotArtifact,
} from "@/types/domain"

const now = () => new Date().toISOString()
const localId = (prefix: string) => `${prefix}-${Math.random().toString(16).slice(2, 8)}`
type LocalAgentEvent = AgentEvent extends infer Event
  ? Event extends AgentEvent
    ? Omit<Event, "id" | "createdAt">
    : never
  : never

export const useWorkbenchStore = defineStore("workbench", () => {
  const projects = ref<Project[]>([])
  const versions = ref<CodeVersion[]>([])
  const conversations = ref<Conversation[]>([])
  const messages = ref<ChatMessage[]>([])
  const runs = ref<RunRecord[]>([])
  const snapshots = ref<SnapshotArtifact[]>([])
  const events = ref<AgentEvent[]>([])
  const currentProjectId = ref<string>("")
  const currentVersionId = ref<string>("")
  const currentConversationId = ref<string>("")
  const code = ref("")
  const isLoading = ref(false)
  const isAgentRunning = ref(false)
  const activeAgentController = ref<AbortController | null>(null)
  const lastRunResult = ref<JscadRunResult | null>(null)
  const currentGeometry = ref<JscadGeometry | null>(null)
  const viewerSnapshotBase64 = ref<string>("")
  const isRepairLoopRunning = ref(false)
  const repairAttempt = ref(0)
  const repairStoppedReason = ref("")
  const stopRepairRequested = ref(false)
  const currentReview = ref<ReviewReport | null>(null)
  const inspectorTab = ref<"code" | "review" | "logs">("code")
  const isReviewRunning = ref(false)
  const reviewError = ref("")
  const configStatus = ref<ConfigStatus | null>(null)
  const isExporting = ref(false)
  const lastExportError = ref("")
  const snapshotProvider = ref<(() => Promise<string | null>) | null>(null)
  const canStopAgent = computed(() => Boolean(activeAgentController.value))

  const currentProject = computed(() => projects.value.find((project) => project.id === currentProjectId.value))
  const currentVersion = computed(() => versions.value.find((version) => version.id === currentVersionId.value))
  const currentConversation = computed(() =>
    conversations.value.find((conversation) => conversation.id === currentConversationId.value),
  )
  const projectConversations = computed(() =>
    conversations.value.filter((conversation) => conversation.projectId === currentProjectId.value),
  )
  const projectVersions = computed(() => versions.value.filter((version) => version.projectId === currentProjectId.value))
  const conversationMessages = computed(() =>
    messages.value.filter((message) => message.conversationId === currentConversationId.value),
  )

  async function refreshCurrentProjectData() {
    if (!currentProjectId.value) {
      return
    }
    const [project, projectVersionsResult, projectConversationsResult] = await Promise.all([
      apiGateway.projects.getProject(currentProjectId.value),
      apiGateway.projects.listVersions(currentProjectId.value),
      apiGateway.projects.listConversations(currentProjectId.value),
    ])

    const existingProjectIndex = projects.value.findIndex((item) => item.id === project.id)
    if (existingProjectIndex >= 0) {
      projects.value[existingProjectIndex] = project
    } else {
      projects.value.unshift(project)
    }

    versions.value = [
      ...versions.value.filter((version) => version.projectId !== project.id),
      ...projectVersionsResult,
    ]
    conversations.value = [
      ...conversations.value.filter((conversation) => conversation.projectId !== project.id),
      ...projectConversationsResult,
    ]
    await loadConversationMessages()
    await loadRuns()
    await loadSnapshots()
  }

  function appendEvent(event: AgentEvent) {
    events.value.unshift(event)
    if (event.type === "vision_review") {
      currentReview.value = event.report
      reviewError.value = ""
      inspectorTab.value = "review"
    }
    if (event.type === "model_error") {
      reviewError.value = event.message
      inspectorTab.value = "logs"
    }
    if (event.type === "assistant_message") {
      messages.value.push({
        id: localId("msg"),
        conversationId: currentConversationId.value,
        role: "assistant",
        content: event.assistantMessage,
        createdAt: event.createdAt,
      })
    }
    if (event.type === "repair_start") {
      isRepairLoopRunning.value = true
      repairStoppedReason.value = ""
    }
    if (event.type === "repair_stopped" || event.type === "user_action_required") {
      isRepairLoopRunning.value = false
      repairStoppedReason.value = event.reason
    }
    if (event.type === "code_patch") {
      code.value = event.code
    }
  }

  function appendLocalEvent(event: LocalAgentEvent) {
    appendEvent({
      ...event,
      id: localId("evt"),
      createdAt: now(),
    } as AgentEvent)
  }

  async function handleAgentEvent(event: AgentEvent, autoRepairAttempt: number): Promise<number> {
    appendEvent(event)
    if (event.type === "code_write_done") {
      currentVersionId.value = event.versionId
      await refreshCurrentProjectData()
      const version = versions.value.find((item) => item.id === event.versionId)
      if (version) {
        code.value = version.code
      }
      return autoRepairAttempt
    }
    if (event.type === "repair_done") {
      repairAttempt.value = autoRepairAttempt + 1
      return repairAttempt.value
    }
    if (event.type === "render_request") {
      if (stopRepairRequested.value) {
        isRepairLoopRunning.value = false
        repairStoppedReason.value = "用户已停止自动修复。"
        appendLocalEvent({ type: "repair_stopped", reason: repairStoppedReason.value })
        return autoRepairAttempt
      }
      await runCurrentCode(autoRepairAttempt, false)
    }
    return autoRepairAttempt
  }

  async function consumeAgentEvents(stream: AsyncIterable<AgentEvent>, autoRepairAttempt = 0) {
    let attempt = autoRepairAttempt
    for await (const event of stream) {
      attempt = await handleAgentEvent(event, attempt)
    }
  }

  async function loadProjects() {
    isLoading.value = true
    try {
      projects.value = await apiGateway.projects.listProjects()
      if (!currentProjectId.value && projects.value[0]) {
        await openProject(projects.value[0].id)
      }
    } finally {
      isLoading.value = false
    }
  }

  async function createProject() {
    const project = await apiGateway.projects.createProject({
      name: `新建项目 ${projects.value.length + 1}`,
      description: "高寒建筑草图项目。",
      region: "高寒地区",
    })
    projects.value.unshift(project)
    await openProject(project.id)
    return project
  }

  async function openProject(projectId: string, conversationId?: string) {
    isLoading.value = true
    try {
      const [project, projectVersionsResult, projectConversationsResult] = await Promise.all([
        apiGateway.projects.getProject(projectId),
        apiGateway.projects.listVersions(projectId),
        apiGateway.projects.listConversations(projectId),
      ])

      const existingProjectIndex = projects.value.findIndex((item) => item.id === project.id)
      if (existingProjectIndex >= 0) {
        projects.value[existingProjectIndex] = project
      }

      versions.value = [
        ...versions.value.filter((version) => version.projectId !== projectId),
        ...projectVersionsResult,
      ]
      conversations.value = [
        ...conversations.value.filter((conversation) => conversation.projectId !== projectId),
        ...projectConversationsResult,
      ]

      currentProjectId.value = project.id
      currentVersionId.value = project.currentVersionId || projectVersionsResult[0]?.id || ""
      currentConversationId.value = conversationId || project.currentConversationId || projectConversationsResult[0]?.id || ""
      const version = projectVersionsResult.find((item) => item.id === currentVersionId.value) || projectVersionsResult[0]
      code.value = version?.code || ""
      events.value = []
      lastRunResult.value = null
      currentGeometry.value = null
      viewerSnapshotBase64.value = ""
      isRepairLoopRunning.value = false
      repairAttempt.value = 0
      repairStoppedReason.value = ""
      stopRepairRequested.value = false
      await loadConversationMessages()
      await loadRuns()
      await loadSnapshots()
    } finally {
      isLoading.value = false
    }
  }

  async function openVersion(versionId: string) {
    const version = versions.value.find((item) => item.id === versionId)
    if (!version) {
      return
    }
    currentVersionId.value = version.id
    code.value = version.code
    lastRunResult.value = null
    repairAttempt.value = 0
    repairStoppedReason.value = ""
  }

  async function openConversation(conversationId: string) {
    currentConversationId.value = conversationId
    await loadConversationMessages()
  }

  async function createConversation() {
    if (!currentProjectId.value) {
      return
    }
    const conversation = await apiGateway.projects.createConversation(currentProjectId.value, "新建对话")
    conversations.value.unshift(conversation)
    currentConversationId.value = conversation.id
    messages.value = messages.value.filter((message) => message.conversationId !== conversation.id)
    await refreshCurrentProjectData()
  }

  async function loadConversationMessages() {
    if (!currentConversationId.value) {
      messages.value = []
      return
    }
    const loaded = await apiGateway.projects.listMessages(currentConversationId.value)
    messages.value = [
      ...messages.value.filter((message) => message.conversationId !== currentConversationId.value),
      ...loaded,
    ]
  }

  async function loadRuns() {
    if (!currentProjectId.value) {
      runs.value = []
      return
    }
    runs.value = await apiGateway.projects.listRuns(currentProjectId.value)
  }

  async function loadSnapshots() {
    if (!currentProjectId.value) {
      snapshots.value = []
      return
    }
    snapshots.value = await apiGateway.projects.listSnapshots(currentProjectId.value)
  }

  async function loadConfigStatus() {
    configStatus.value = await apiGateway.projects.getConfigStatus()
  }

  async function sendMessage(content: string) {
    if (!content.trim() || !currentProjectId.value || !currentConversationId.value) {
      return
    }
    const conversationId = currentConversationId.value
    messages.value.push({
      id: localId("msg"),
      conversationId,
      role: "user",
      content: content.trim(),
      createdAt: now(),
    })
    isAgentRunning.value = true
    const controller = new AbortController()
    activeAgentController.value = controller
    reviewError.value = ""
    stopRepairRequested.value = false
    repairAttempt.value = 0
    repairStoppedReason.value = ""
    try {
      for await (const event of apiGateway.agent.sendMessage({
        projectId: currentProjectId.value,
        conversationId,
        message: content.trim(),
        currentVersionId: currentVersionId.value,
      }, { signal: controller.signal })) {
        await handleAgentEvent(event, 0)
      }
      await refreshCurrentProjectData()
    } catch (error) {
      if (error instanceof DOMException && error.name === "AbortError") {
        appendLocalEvent({ type: "error", message: "用户已终止本次对话/生成，未完成的版本不会写入。", recoverable: true })
        return
      }
      throw error
    } finally {
      isAgentRunning.value = false
      if (activeAgentController.value === controller) {
        activeAgentController.value = null
      }
    }
  }

  async function runCurrentCode(autoRepairAttempt = 0, emitLocalRequest = true) {
    if (!currentProjectId.value || !currentVersionId.value || !currentConversationId.value) {
      appendLocalEvent({ type: "error", message: "当前项目还没有真实 AI 生成的代码版本。请先在对话中描述需求生成首个版本。", recoverable: true })
      return
    }
    if (emitLocalRequest) {
      appendLocalEvent({ type: "render_request", reason: "用户触发代码运行。" })
    }
    const versionId = currentVersionId.value
    const localResult = await runJscadCode(code.value, versionId)
    if (localResult.ok && localResult.geometry) {
      currentGeometry.value = localResult.geometry
    }
    const { geometry: _geometry, ...serializableResult } = localResult
    const result = {
      ...serializableResult,
      projectId: currentProjectId.value,
      conversationId: currentConversationId.value,
      autoRepairAttempt,
    }
    lastRunResult.value = result
    repairAttempt.value = autoRepairAttempt
    await consumeAgentEvents(apiGateway.agent.submitRenderResult(result), autoRepairAttempt)
    await refreshCurrentProjectData()
  }

  function updateViewerSnapshot(snapshot: string) {
    viewerSnapshotBase64.value = snapshot
  }

  function registerSnapshotProvider(provider: (() => Promise<string | null>) | null) {
    snapshotProvider.value = provider
  }

  function stopRepairLoop() {
    stopRepairRequested.value = true
    isRepairLoopRunning.value = false
    repairStoppedReason.value = "用户已停止自动修复。"
    stopActiveAgent()
    appendLocalEvent({ type: "repair_stopped", reason: repairStoppedReason.value })
  }

  function stopActiveAgent() {
    activeAgentController.value?.abort()
    activeAgentController.value = null
    isAgentRunning.value = false
    isReviewRunning.value = false
  }

  async function captureCurrentSnapshot() {
    const captured = await snapshotProvider.value?.()
    if (captured) {
      viewerSnapshotBase64.value = captured
      return captured
    }
    return viewerSnapshotBase64.value || ""
  }

  async function saveCurrentSnapshot(source = "canvas", imageBase64?: string) {
    const snapshotImage = imageBase64 || viewerSnapshotBase64.value
    if (!currentProjectId.value || !currentVersionId.value || !snapshotImage) {
      return null
    }
    const snapshot = await apiGateway.projects.saveSnapshot(currentProjectId.value, {
      versionId: currentVersionId.value,
      conversationId: currentConversationId.value || undefined,
      imageBase64: snapshotImage,
      source,
    })
    snapshots.value = [snapshot, ...snapshots.value.filter((item) => item.id !== snapshot.id)]
    return snapshot
  }

  function exportFilename(format: ExportFormat) {
    const projectName = currentProject.value?.name || "arcticcad"
    const versionLabel = currentVersion.value?.label || currentVersionId.value || "version"
    const stamp = new Date().toISOString().replace(/[-:]/g, "").replace(/\..+/, "").replace("T", "-")
    const safe = `${projectName}-${versionLabel}-${stamp}`.replace(/[\\/:*?"<>|\s]+/g, "-")
    return `${safe}.${format}`
  }

  async function exportCurrentGeometry(format: ExportFormat) {
    isExporting.value = true
    lastExportError.value = ""
    try {
      if (format === "svg") {
        if (!viewerSnapshotBase64.value) {
          throw new Error("当前画布还没有可导出的截图。")
        }
        exportSnapshotSvg(viewerSnapshotBase64.value, exportFilename("svg"))
        return
      }
      if (!currentGeometry.value) {
        throw new Error("当前版本还没有可导出的 JSCAD geometry。")
      }
      if (format === "stl") {
        await exportStl(currentGeometry.value, exportFilename("stl"))
      } else {
        await exportDxf(currentGeometry.value, exportFilename("dxf"))
      }
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error)
      lastExportError.value = message
      appendLocalEvent({ type: "error", message, recoverable: true })
    } finally {
      isExporting.value = false
    }
  }

  async function applyReviewSuggestion(suggestion: string) {
    await sendMessage(`请根据视觉模型审图建议修改当前 JSCAD 模型：${suggestion}`)
  }

  async function requestReview() {
    if (!currentProjectId.value || !currentVersionId.value) {
      reviewError.value = "当前项目还没有真实 AI 生成的代码版本，无法审图。"
      appendLocalEvent({ type: "error", message: reviewError.value, recoverable: true })
      return
    }
    isAgentRunning.value = true
    isReviewRunning.value = true
    const controller = new AbortController()
    activeAgentController.value = controller
    reviewError.value = ""
    let snapshotId: string | undefined
    try {
      try {
        const snapshotImage = await captureCurrentSnapshot()
        const snapshot = await saveCurrentSnapshot("review", snapshotImage)
        snapshotId = snapshot?.id
        if (snapshot) {
          const sizeText = snapshot.byteSize ? `${Math.round(snapshot.byteSize / 1024)} KB` : "unknown size"
          appendLocalEvent({
            type: "tool_progress",
            tool: "qwen_vision_review",
            progress: 0,
            message: `已保存当前视角截图：${snapshot.mimeType || "image"}，${sizeText}。`,
          })
        }
      } catch (error) {
        appendLocalEvent({
          type: "error",
          message: `画布截图保存失败，将降级为仅代码审图：${error instanceof Error ? error.message : String(error)}`,
          recoverable: true,
        })
      }
      for await (const event of apiGateway.agent.requestReview({
        projectId: currentProjectId.value,
        versionId: currentVersionId.value,
        snapshotId,
        reviewMode: "review",
        userRequirement: "审查当前高寒建筑草图。",
      }, { signal: controller.signal })) {
        appendEvent(event)
      }
    } catch (error) {
      if (error instanceof DOMException && error.name === "AbortError") {
        reviewError.value = "用户已终止本次审图。"
        appendLocalEvent({ type: "error", message: reviewError.value, recoverable: true })
        return
      }
      throw error
    } finally {
      isAgentRunning.value = false
      isReviewRunning.value = false
      if (activeAgentController.value === controller) {
        activeAgentController.value = null
      }
    }
  }

  return {
    projects,
    versions,
    conversations,
    messages,
    runs,
    snapshots,
    events,
    currentProjectId,
    currentVersionId,
    currentConversationId,
    code,
    isLoading,
    isAgentRunning,
    canStopAgent,
    lastRunResult,
    currentGeometry,
    viewerSnapshotBase64,
    isRepairLoopRunning,
    repairAttempt,
    repairStoppedReason,
    currentReview,
    inspectorTab,
    isReviewRunning,
    reviewError,
    configStatus,
    isExporting,
    lastExportError,
    currentProject,
    currentVersion,
    currentConversation,
    projectConversations,
    projectVersions,
    conversationMessages,
    loadProjects,
    createProject,
    openProject,
    openVersion,
    openConversation,
    createConversation,
    loadRuns,
    loadSnapshots,
    loadConfigStatus,
    sendMessage,
    runCurrentCode,
    updateViewerSnapshot,
    registerSnapshotProvider,
    stopRepairLoop,
    stopActiveAgent,
    saveCurrentSnapshot,
    exportCurrentGeometry,
    applyReviewSuggestion,
    requestReview,
  }
})

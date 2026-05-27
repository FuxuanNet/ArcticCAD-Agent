<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, shallowRef, watch } from "vue"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Progress } from "@/components/ui/progress"
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip"
import { useWorkbenchStore } from "@/stores/workbench"
import { AlertTriangle, Box, Camera, Home, RotateCcw, ScanSearch, Square, StopCircle, ZoomIn, ZoomOut } from "lucide-vue-next"

type ReglRenderer = typeof import("@jscad/regl-renderer")
type ViewerState = {
  renderer: ReglRenderer
  render: (options: Record<string, unknown>) => void
  camera: Record<string, unknown>
  controls: Record<string, unknown>
  entities: unknown[]
  animationId: number
  lastPointer: { x: number; y: number } | null
  dragMode: "rotate" | "pan"
}

const store = useWorkbenchStore()
const container = ref<HTMLElement | null>(null)
const canvas = ref<HTMLCanvasElement | null>(null)
const viewer = shallowRef<ViewerState | null>(null)

const statusText = computed(() => {
  if (store.isRepairLoopRunning) {
    return `修复第 ${store.repairAttempt + 1} 轮`
  }
  if (!store.lastRunResult) {
    return "等待运行"
  }
  return store.lastRunResult.ok ? "运行成功" : "运行失败"
})

const hasGeometry = computed(() => Boolean(store.currentGeometry))

function mergeState(target: Record<string, unknown>, patch?: Record<string, unknown>) {
  if (!patch) return
  Object.assign(target, patch)
}

function canvasSize() {
  const host = container.value
  return {
    width: Math.max(320, Math.floor(host?.clientWidth || 320)),
    height: Math.max(240, Math.floor(host?.clientHeight || 240)),
  }
}

async function initViewer() {
  if (!container.value || viewer.value) return
  const renderer = await import("@jscad/regl-renderer")
  const camera = { ...renderer.cameras.perspective.defaults }
  const controls = { ...renderer.controls.orbit.defaults }
  const { width, height } = canvasSize()
  renderer.cameras.perspective.setProjection(camera, camera, { width, height })
  renderer.cameras.perspective.update(camera, camera)
  const render = (renderer.prepareRender as unknown as (options: Record<string, unknown>) => (options: Record<string, unknown>) => void)({
    glOptions: { container: container.value, attributes: { preserveDrawingBuffer: true } },
    camera,
    drawCommands: {
      drawAxis: renderer.drawCommands.drawAxis,
      drawGrid: renderer.drawCommands.drawGrid,
      drawLines: renderer.drawCommands.drawLines,
      drawMesh: renderer.drawCommands.drawMesh,
    },
    rendering: {
      background: [0.98, 0.99, 1, 1],
      meshColor: [0.1, 0.48, 0.72, 1],
    },
    entities: [],
  })
  canvas.value = container.value.querySelector("canvas")
  if (canvas.value) {
    canvas.value.style.width = "100%"
    canvas.value.style.height = "100%"
    canvas.value.style.display = "block"
  }
  viewer.value = {
    renderer,
    render,
    camera,
    controls,
    entities: [],
    animationId: 0,
    lastPointer: null,
    dragMode: "rotate",
  }
  updateEntities(true)
  startLoop()
}

function baseEntities(size = 500) {
  return [
    { visuals: { drawCmd: "drawGrid", show: true }, size: [size, size], ticks: [25, 5] },
    { visuals: { drawCmd: "drawAxis", show: true }, size: size * 0.35 },
  ]
}

function updateEntities(fit = false) {
  const state = viewer.value
  if (!state) return
  const solids = store.currentGeometry
    ? (state.renderer.entitiesFromSolids as unknown as (options: Record<string, unknown>, solids: unknown) => unknown[])({}, store.currentGeometry)
    : []
  state.entities = [...baseEntities(), ...solids]
  if (fit && solids.length > 0) {
    const next = state.renderer.controls.orbit.zoomToFit({
      controls: state.controls as never,
      camera: state.camera as never,
      entities: solids as never,
    })
    mergeState(state.controls, next.controls as Record<string, unknown>)
    mergeState(state.camera, next.camera as Record<string, unknown>)
  }
  renderFrame()
}

function renderFrame() {
  const state = viewer.value
  if (!state) return
  const { width, height } = canvasSize()
  state.renderer.cameras.perspective.setProjection(state.camera as never, state.camera as never, { width, height })
  const next = state.renderer.controls.orbit.update({
    controls: state.controls as never,
    camera: state.camera as never,
  })
  mergeState(state.controls, next.controls as Record<string, unknown>)
  mergeState(state.camera, next.camera as Record<string, unknown>)
  state.render({
    camera: state.camera,
    drawCommands: {
      drawAxis: state.renderer.drawCommands.drawAxis,
      drawGrid: state.renderer.drawCommands.drawGrid,
      drawLines: state.renderer.drawCommands.drawLines,
      drawMesh: state.renderer.drawCommands.drawMesh,
    },
    rendering: {
      background: [0.98, 0.99, 1, 1],
      meshColor: [0.1, 0.48, 0.72, 1],
      lightPosition: [150, 220, 260],
      ambientLightAmount: 0.42,
      diffuseLightAmount: 0.82,
    },
    entities: state.entities,
  })
  captureSnapshot()
}

function startLoop() {
  const state = viewer.value
  if (!state) return
  const tick = () => {
    renderFrame()
    state.animationId = window.requestAnimationFrame(tick)
  }
  state.animationId = window.requestAnimationFrame(tick)
}

function captureSnapshot() {
  if (!canvas.value) return
  try {
    store.updateViewerSnapshot(canvas.value.toDataURL("image/png"))
  } catch {
    // WebGL screenshots can fail on some drivers; review still falls back to code-only.
  }
}

function blobToDataUrl(blob: Blob) {
  return new Promise<string>((resolve, reject) => {
    const reader = new FileReader()
    reader.onload = () => resolve(String(reader.result || ""))
    reader.onerror = () => reject(reader.error || new Error("Failed to read image blob."))
    reader.readAsDataURL(blob)
  })
}

function canvasToBlob(source: HTMLCanvasElement, type: string, quality?: number) {
  return new Promise<Blob | null>((resolve) => {
    source.toBlob((blob) => resolve(blob), type, quality)
  })
}

async function captureReviewSnapshot() {
  if (!canvas.value) return null
  renderFrame()
  const source = canvas.value
  const maxSide = 1024
  const scale = Math.min(1, maxSide / Math.max(source.width || 1, source.height || 1))
  const width = Math.max(1, Math.round((source.width || 1) * scale))
  const height = Math.max(1, Math.round((source.height || 1) * scale))
  const target = document.createElement("canvas")
  target.width = width
  target.height = height
  const context = target.getContext("2d")
  if (!context) {
    return source.toDataURL("image/png")
  }
  context.drawImage(source, 0, 0, width, height)
  const webp = await canvasToBlob(target, "image/webp", 0.78)
  const blob = webp || (await canvasToBlob(target, "image/jpeg", 0.82)) || (await canvasToBlob(target, "image/png"))
  const dataUrl = blob ? await blobToDataUrl(blob) : target.toDataURL("image/png")
  store.updateViewerSnapshot(dataUrl)
  return dataUrl
}

function resetView() {
  const state = viewer.value
  if (!state) return
  Object.assign(state.camera, state.renderer.cameras.perspective.defaults)
  const { width, height } = canvasSize()
  state.renderer.cameras.perspective.setProjection(state.camera as never, state.camera as never, { width, height })
  state.renderer.cameras.perspective.update(state.camera as never, state.camera as never)
  state.controls = { ...state.renderer.controls.orbit.defaults }
  updateEntities(true)
}

function setPresetView(view: "front" | "back" | "left" | "right" | "top") {
  const state = viewer.value
  if (!state) return
  const next = state.renderer.cameras.camera.toPresetView(view, { camera: state.camera as never })
  mergeState(state.camera, next as Record<string, unknown>)
  renderFrame()
}

function zoom(delta: number) {
  const state = viewer.value
  if (!state) return
  const next = state.renderer.controls.orbit.zoom({
    controls: state.controls as never,
    camera: state.camera as never,
    speed: 0.08,
  }, delta)
  mergeState(state.controls, next.controls as Record<string, unknown>)
  mergeState(state.camera, next.camera as Record<string, unknown>)
  renderFrame()
}

function onPointerDown(event: PointerEvent) {
  const state = viewer.value
  if (!state) return
  state.dragMode = event.shiftKey || event.button === 1 ? "pan" : "rotate"
  state.lastPointer = { x: event.clientX, y: event.clientY }
  canvas.value?.setPointerCapture(event.pointerId)
}

function onPointerMove(event: PointerEvent) {
  const state = viewer.value
  if (!state?.lastPointer) return
  const dx = event.clientX - state.lastPointer.x
  const dy = event.clientY - state.lastPointer.y
  state.lastPointer = { x: event.clientX, y: event.clientY }
  const next =
    state.dragMode === "pan"
      ? state.renderer.controls.orbit.pan({ controls: state.controls as never, camera: state.camera as never, speed: 0.75 }, [dx, dy])
      : state.renderer.controls.orbit.rotate({ controls: state.controls as never, camera: state.camera as never, speed: 0.006 }, [dx, dy])
  mergeState(state.controls, next.controls as Record<string, unknown>)
  mergeState(state.camera, next.camera as Record<string, unknown>)
  renderFrame()
}

function onPointerUp(event: PointerEvent) {
  viewer.value!.lastPointer = null
  canvas.value?.releasePointerCapture(event.pointerId)
}

function onWheel(event: WheelEvent) {
  event.preventDefault()
  zoom(event.deltaY > 0 ? 0.12 : -0.12)
}

onMounted(async () => {
  await nextTick()
  await initViewer()
  store.registerSnapshotProvider(captureReviewSnapshot)
  window.addEventListener("resize", renderFrame)
})

onBeforeUnmount(() => {
  window.removeEventListener("resize", renderFrame)
  store.registerSnapshotProvider(null)
  if (viewer.value?.animationId) {
    window.cancelAnimationFrame(viewer.value.animationId)
  }
})

watch(() => store.currentGeometry, () => updateEntities(true))
</script>

<template>
  <section class="flex h-full min-h-0 flex-col bg-background">
    <div class="flex h-10 items-center justify-between border-b border-border px-3">
      <div class="flex items-center gap-2">
        <Box />
        <span class="text-sm font-medium">JSCAD 画布</span>
        <Badge variant="outline">{{ statusText }}</Badge>
      </div>
      <div class="flex items-center gap-1">
        <TooltipProvider>
          <Tooltip>
            <TooltipTrigger as-child>
              <Button variant="ghost" size="icon" @click="resetView">
                <Home />
              </Button>
            </TooltipTrigger>
            <TooltipContent>适配模型</TooltipContent>
          </Tooltip>
          <Tooltip>
            <TooltipTrigger as-child>
              <Button variant="ghost" size="icon" @click="zoom(-0.12)">
                <ZoomIn />
              </Button>
            </TooltipTrigger>
            <TooltipContent>放大</TooltipContent>
          </Tooltip>
          <Tooltip>
            <TooltipTrigger as-child>
              <Button variant="ghost" size="icon" @click="zoom(0.12)">
                <ZoomOut />
              </Button>
            </TooltipTrigger>
            <TooltipContent>缩小</TooltipContent>
          </Tooltip>
        </TooltipProvider>
      </div>
    </div>

    <div class="relative min-h-0 flex-1 overflow-hidden bg-slate-50">
      <div
        ref="container"
        class="absolute inset-0 cursor-grab active:cursor-grabbing"
        @pointerdown="onPointerDown"
        @pointermove="onPointerMove"
        @pointerup="onPointerUp"
        @pointercancel="onPointerUp"
        @wheel="onWheel"
      />

      <div class="absolute left-3 top-3 flex flex-wrap items-center gap-1 rounded-md border border-border bg-background/90 p-1 shadow-sm backdrop-blur">
        <Button variant="ghost" size="sm" @click="setPresetView('front')">前</Button>
        <Button variant="ghost" size="sm" @click="setPresetView('back')">后</Button>
        <Button variant="ghost" size="sm" @click="setPresetView('left')">左</Button>
        <Button variant="ghost" size="sm" @click="setPresetView('right')">右</Button>
        <Button variant="ghost" size="sm" @click="setPresetView('top')">顶</Button>
      </div>

      <div class="absolute right-3 top-3 flex items-center gap-2 rounded-md border border-border bg-background/90 px-2 py-1 text-xs shadow-sm backdrop-blur">
        <Camera class="size-4" />
        <span>{{ store.viewerSnapshotBase64 ? "截图已就绪" : "等待截图" }}</span>
      </div>

      <div v-if="!hasGeometry" class="absolute inset-0 flex items-center justify-center">
        <div class="flex items-center gap-2 rounded-md border border-border bg-background/90 px-3 py-2 text-sm text-muted-foreground shadow-sm">
          <Square class="size-4" />
          {{ store.currentVersionId ? "等待 JSCAD 运行结果" : "等待真实 AI 生成首个版本" }}
        </div>
      </div>

      <div class="absolute bottom-3 left-3 right-3 grid gap-2">
        <Alert v-if="store.lastRunResult?.error" variant="destructive" class="rounded-md">
          <AlertTriangle />
          <AlertTitle>{{ store.lastRunResult.error.kind }} error</AlertTitle>
          <AlertDescription>{{ store.lastRunResult.error.message }}</AlertDescription>
        </Alert>
        <div v-if="store.isRepairLoopRunning" class="rounded-md border border-border bg-background/95 p-3 shadow-sm">
          <div class="mb-2 flex items-center justify-between gap-2 text-xs">
            <span class="flex items-center gap-2">
              <RotateCcw class="size-4" />
              自动修复进行中
            </span>
            <Button variant="outline" size="sm" @click="store.stopRepairLoop">
              <StopCircle data-icon="inline-start" />
              停止
            </Button>
          </div>
          <Progress :model-value="Math.min(95, 20 + store.repairAttempt * 10)" />
        </div>
        <div v-if="store.repairStoppedReason" class="flex items-center gap-2 rounded-md border border-border bg-background/95 px-3 py-2 text-xs shadow-sm">
          <ScanSearch class="size-4" />
          {{ store.repairStoppedReason }}
        </div>
      </div>
    </div>
  </section>
</template>

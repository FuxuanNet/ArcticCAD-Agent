<script setup lang="ts">
import { computed } from "vue"
import { useRouter } from "vue-router"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuGroup,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { useWorkbenchStore } from "@/stores/workbench"
import { Bot, Download, Loader2, MessageSquare, Play, ScanSearch, Settings, StopCircle } from "lucide-vue-next"

const props = defineProps<{
  onOpenChat: () => void
}>()

const store = useWorkbenchStore()
const router = useRouter()

const runLabel = computed(() => (store.lastRunResult?.ok ? "已渲染" : "运行"))
</script>

<template>
  <header class="flex h-14 shrink-0 items-center justify-between gap-3 border-b border-border bg-background px-3">
    <div class="flex min-w-0 items-center gap-3">
      <div class="min-w-0">
        <h2 class="truncate text-sm font-semibold">{{ store.currentProject?.name || "工作台" }}</h2>
        <p class="truncate text-xs text-muted-foreground">{{ store.currentConversation?.title || "项目对话" }}</p>
      </div>
      <Badge variant="secondary">{{ store.currentVersion?.label || "no version" }}</Badge>
    </div>

    <div class="flex items-center gap-2">
      <Button variant="outline" size="sm" :disabled="store.isAgentRunning || !store.currentVersionId" @click="() => store.runCurrentCode()">
        <Play data-icon="inline-start" />
        {{ runLabel }}
      </Button>
      <Button variant="outline" size="sm" :disabled="store.isAgentRunning || !store.currentVersionId" @click="store.requestReview">
        <Loader2 v-if="store.isReviewRunning" data-icon="inline-start" class="animate-spin" />
        <ScanSearch v-else data-icon="inline-start" />
        {{ store.isReviewRunning ? "审图中" : "审图" }}
      </Button>
      <Button variant="outline" size="sm" @click="props.onOpenChat">
        <MessageSquare data-icon="inline-start" />
        对话
      </Button>
      <Button v-if="store.canStopAgent" variant="outline" size="sm" @click="store.stopActiveAgent">
        <StopCircle data-icon="inline-start" />
        停止
      </Button>
      <DropdownMenu>
        <DropdownMenuTrigger as-child>
          <Button variant="outline" size="sm" :disabled="store.isExporting">
            <Download data-icon="inline-start" />
            导出
          </Button>
        </DropdownMenuTrigger>
        <DropdownMenuContent align="end" class="w-44">
          <DropdownMenuLabel>导出格式</DropdownMenuLabel>
          <DropdownMenuSeparator />
          <DropdownMenuGroup>
            <DropdownMenuItem :disabled="!store.viewerSnapshotBase64" @click="store.exportCurrentGeometry('svg')">
              SVG 预览图
            </DropdownMenuItem>
            <DropdownMenuItem :disabled="!store.currentGeometry" @click="store.exportCurrentGeometry('stl')">
              STL 模型
            </DropdownMenuItem>
            <DropdownMenuItem :disabled="!store.currentGeometry" @click="store.exportCurrentGeometry('dxf')">
              DXF 草图
            </DropdownMenuItem>
          </DropdownMenuGroup>
        </DropdownMenuContent>
      </DropdownMenu>
      <Button variant="ghost" size="icon" @click="router.push('/settings')">
        <Settings />
      </Button>
      <Badge v-if="store.isAgentRunning">
        <Bot data-icon="inline-start" />
        模型处理中
      </Badge>
    </div>
  </header>
</template>

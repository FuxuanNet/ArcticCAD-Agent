<script setup lang="ts">
import { computed, onMounted } from "vue"
import { RouterLink } from "vue-router"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Separator } from "@/components/ui/separator"
import { useWorkbenchStore } from "@/stores/workbench"
import { ArrowLeft, CircleAlert, CircleCheck, RefreshCw, Server } from "lucide-vue-next"

const store = useWorkbenchStore()
const apiBaseUrl = computed(() => import.meta.env.VITE_API_BASE_URL || "同源 /api")

onMounted(() => {
  void store.loadConfigStatus()
})

function statusVariant(status?: string) {
  return status === "configured" ? "secondary" : "outline"
}
</script>

<template>
  <main class="min-h-screen bg-background text-foreground">
    <header class="flex h-14 items-center justify-between border-b border-border px-5">
      <div class="flex items-center gap-3">
        <RouterLink to="/projects">
          <Button variant="ghost" size="icon">
            <ArrowLeft />
          </Button>
        </RouterLink>
        <div>
          <h1 class="text-sm font-semibold">设置</h1>
          <p class="text-xs text-muted-foreground">API、模型与项目存储状态</p>
        </div>
      </div>
      <Button variant="outline" size="sm" @click="store.loadConfigStatus">
        <RefreshCw data-icon="inline-start" />
        刷新
      </Button>
    </header>

    <section class="mx-auto flex max-w-4xl flex-col gap-4 px-5 py-5">
      <div class="rounded-md border border-border bg-card">
        <div class="flex items-center justify-between gap-4 px-4 py-3">
          <div class="flex min-w-0 items-center gap-3">
            <Server />
            <div class="min-w-0">
              <h2 class="truncate text-sm font-medium">API Gateway</h2>
              <p class="truncate text-xs text-muted-foreground">{{ apiBaseUrl }}</p>
            </div>
          </div>
          <Badge>后端 API</Badge>
        </div>
        <Separator />
        <div class="grid gap-3 px-4 py-3 text-sm">
          <div class="grid grid-cols-[1fr_auto] items-center gap-3">
            <span>
              <span class="block font-medium">DeepSeek</span>
              <span class="block truncate text-xs text-muted-foreground">
                {{ store.configStatus?.llm.baseUrl || "未读取" }} · {{ store.configStatus?.llm.model || "unknown" }}
              </span>
            </span>
            <Badge :variant="statusVariant(store.configStatus?.llm.status)">
              <CircleCheck v-if="store.configStatus?.llm.status === 'configured'" data-icon="inline-start" />
              <CircleAlert v-else data-icon="inline-start" />
              {{ store.configStatus?.llm.status || "loading" }}
            </Badge>
          </div>
          <div class="grid grid-cols-[1fr_auto] items-center gap-3">
            <span>
              <span class="block font-medium">Qwen Vision</span>
              <span class="block truncate text-xs text-muted-foreground">
                {{ store.configStatus?.vision.baseUrl || "未读取" }} · {{ store.configStatus?.vision.model || "unknown" }}
              </span>
            </span>
            <Badge :variant="statusVariant(store.configStatus?.vision.status)">
              <CircleCheck v-if="store.configStatus?.vision.status === 'configured'" data-icon="inline-start" />
              <CircleAlert v-else data-icon="inline-start" />
              {{ store.configStatus?.vision.status || "loading" }}
            </Badge>
          </div>
          <Separator />
          <div class="flex items-center justify-between gap-3">
            <span class="text-muted-foreground">Projects Dir</span>
            <span class="truncate text-right">{{ store.configStatus?.projectsDir || "未读取" }}</span>
          </div>
          <div class="flex items-center justify-between gap-3">
            <span class="text-muted-foreground">模型超时</span>
            <span class="truncate text-right">{{ store.configStatus?.llmTimeoutSeconds || 0 }} 秒</span>
          </div>
        </div>
      </div>
    </section>
  </main>
</template>

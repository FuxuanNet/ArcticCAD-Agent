<script setup lang="ts">
import { onMounted } from "vue"
import { useRouter } from "vue-router"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Separator } from "@/components/ui/separator"
import { Skeleton } from "@/components/ui/skeleton"
import { useWorkbenchStore } from "@/stores/workbench"
import { FolderPlus, Settings, Snowflake } from "lucide-vue-next"

const store = useWorkbenchStore()
const router = useRouter()

onMounted(() => {
  void store.loadProjects()
})

async function createProject() {
  const project = await store.createProject()
  void router.push(`/projects/${project.id}`)
}
</script>

<template>
  <main class="min-h-screen bg-background text-foreground">
    <header class="flex h-14 items-center justify-between border-b border-border px-5">
      <div class="flex items-center gap-3">
        <div class="flex size-8 items-center justify-center rounded-md border border-border bg-card">
          <Snowflake />
        </div>
        <div class="min-w-0">
          <h1 class="truncate text-sm font-semibold">寒地智建</h1>
          <p class="truncate text-xs text-muted-foreground">ArcticCAD-Agent 工作区</p>
        </div>
      </div>
      <div class="flex items-center gap-2">
        <Button variant="outline" size="sm" @click="router.push('/settings')">
          <Settings data-icon="inline-start" />
          设置
        </Button>
        <Button size="sm" @click="createProject">
          <FolderPlus data-icon="inline-start" />
          新建项目
        </Button>
      </div>
    </header>

    <section class="mx-auto flex max-w-6xl flex-col gap-4 px-5 py-5">
      <div class="flex items-end justify-between gap-4">
        <div class="min-w-0">
          <h2 class="text-lg font-semibold">项目</h2>
          <p class="text-sm text-muted-foreground">选择项目进入 JSCAD 生成、审图和修复工作台。</p>
        </div>
        <Badge variant="secondary">{{ store.projects.length }} 个项目</Badge>
      </div>
      <Separator />

      <div v-if="store.isLoading" class="grid gap-2">
        <Skeleton v-for="item in 3" :key="item" class="h-20 w-full rounded-md" />
      </div>
      <div v-else class="grid gap-2">
        <button
          v-for="project in store.projects"
          :key="project.id"
          class="grid grid-cols-[1fr_auto] items-center gap-4 rounded-md border border-border bg-card px-4 py-3 text-left transition hover:bg-accent"
          @click="router.push(`/projects/${project.id}`)"
        >
          <span class="min-w-0">
            <span class="block truncate text-sm font-medium">{{ project.name }}</span>
            <span class="block truncate text-xs text-muted-foreground">{{ project.description }}</span>
          </span>
          <span class="flex items-center gap-2">
            <Badge variant="outline">{{ project.region }}</Badge>
            <Badge>{{ project.currentVersionId }}</Badge>
          </span>
        </button>
      </div>
    </section>
  </main>
</template>

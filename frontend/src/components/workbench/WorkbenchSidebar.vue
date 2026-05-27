<script setup lang="ts">
import { useRouter } from "vue-router"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { ScrollArea } from "@/components/ui/scroll-area"
import { Separator } from "@/components/ui/separator"
import { useWorkbenchStore } from "@/stores/workbench"
import { Clock3, FileCode2, FolderPlus, MessageSquarePlus, PackageOpen, Settings } from "lucide-vue-next"

const store = useWorkbenchStore()
const router = useRouter()
</script>

<template>
  <aside class="flex h-full w-[248px] shrink-0 flex-col border-r border-border bg-sidebar text-sidebar-foreground">
    <div class="flex h-14 items-center justify-between gap-2 px-3">
      <div class="min-w-0">
        <h1 class="truncate text-sm font-semibold">寒地智建</h1>
        <p class="truncate text-xs text-muted-foreground">CAD Agent 工作台</p>
      </div>
      <Button variant="ghost" size="icon" @click="router.push('/settings')">
        <Settings />
      </Button>
    </div>
    <Separator />

    <ScrollArea class="min-h-0 flex-1">
      <div class="flex flex-col gap-4 p-3">
        <section class="flex flex-col gap-2">
          <div class="flex items-center justify-between gap-2">
            <span class="text-xs font-medium text-muted-foreground">项目</span>
            <Button variant="ghost" size="icon" @click="store.createProject">
              <FolderPlus />
            </Button>
          </div>
          <button
            v-for="project in store.projects"
            :key="project.id"
            class="flex flex-col gap-1 rounded-md px-2 py-2 text-left text-sm transition hover:bg-sidebar-accent"
            :class="{ 'bg-sidebar-accent': project.id === store.currentProjectId }"
            @click="router.push(`/projects/${project.id}/conversations/${project.currentConversationId}`)"
          >
            <span class="flex min-w-0 items-center gap-2">
              <PackageOpen />
              <span class="truncate font-medium">{{ project.name }}</span>
            </span>
            <span class="truncate pl-6 text-xs text-muted-foreground">{{ project.region }}</span>
          </button>
        </section>

        <section class="flex flex-col gap-2">
          <div class="flex items-center justify-between gap-2">
            <span class="text-xs font-medium text-muted-foreground">版本</span>
            <Badge variant="outline">{{ store.projectVersions.length }}</Badge>
          </div>
          <button
            v-for="version in store.projectVersions"
            :key="version.id"
            class="grid grid-cols-[1fr_auto] items-center gap-2 rounded-md px-2 py-2 text-left text-sm transition hover:bg-sidebar-accent"
            :class="{ 'bg-sidebar-accent': version.id === store.currentVersionId }"
            @click="store.openVersion(version.id)"
          >
            <span class="min-w-0">
              <span class="flex min-w-0 items-center gap-2">
                <FileCode2 />
                <span class="truncate">{{ version.label }}</span>
              </span>
              <span class="block truncate pl-6 text-xs text-muted-foreground">{{ version.summary }}</span>
            </span>
            <Badge variant="secondary">{{ version.status }}</Badge>
          </button>
        </section>

        <section class="flex flex-col gap-2">
          <div class="flex items-center justify-between gap-2">
            <span class="text-xs font-medium text-muted-foreground">对话</span>
            <Button variant="ghost" size="icon" @click="store.createConversation">
              <MessageSquarePlus />
            </Button>
          </div>
          <button
            v-for="conversation in store.projectConversations"
            :key="conversation.id"
            class="flex flex-col gap-1 rounded-md px-2 py-2 text-left text-sm transition hover:bg-sidebar-accent"
            :class="{ 'bg-sidebar-accent': conversation.id === store.currentConversationId }"
            @click="router.push(`/projects/${store.currentProjectId}/conversations/${conversation.id}`)"
          >
            <span class="truncate font-medium">{{ conversation.title }}</span>
            <span class="flex items-center gap-1 text-xs text-muted-foreground">
              <Clock3 />
              {{ conversation.messageCount }} 条消息
            </span>
          </button>
        </section>
      </div>
    </ScrollArea>

    <Separator />
    <div class="grid gap-2 p-3 text-xs">
      <div class="flex items-center justify-between gap-2">
        <span class="text-muted-foreground">运行记录</span>
        <Badge variant="outline">{{ store.runs.length }} 次</Badge>
      </div>
      <div class="flex items-center justify-between gap-2">
        <span class="text-muted-foreground">最近运行</span>
        <Badge :variant="store.runs[0]?.ok ? 'secondary' : 'outline'">
          {{ store.runs[0] ? (store.runs[0].ok ? "成功" : store.runs[0].error?.kind || "失败") : "暂无" }}
        </Badge>
      </div>
      <div class="flex items-center justify-between gap-2">
        <span class="text-muted-foreground">截图归档</span>
        <Badge variant="outline">{{ store.snapshots.length }} 张</Badge>
      </div>
    </div>
  </aside>
</template>

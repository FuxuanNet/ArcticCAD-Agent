<script setup lang="ts">
import { onMounted, watch } from "vue"
import { useRoute, useRouter } from "vue-router"
import WorkbenchShell from "@/components/workbench/WorkbenchShell.vue"
import { useWorkbenchStore } from "@/stores/workbench"

const route = useRoute()
const router = useRouter()
const store = useWorkbenchStore()

async function syncRoute() {
  const projectId = String(route.params.projectId || "")
  const conversationId = route.params.conversationId ? String(route.params.conversationId) : undefined
  if (!projectId) {
    return
  }
  await store.loadProjects()
  await store.openProject(projectId, conversationId)
  if (!conversationId && store.currentConversationId) {
    void router.replace(`/projects/${projectId}/conversations/${store.currentConversationId}`)
  }
}

onMounted(() => {
  void syncRoute()
})

watch(
  () => [route.params.projectId, route.params.conversationId],
  () => {
    void syncRoute()
  },
)
</script>

<template>
  <WorkbenchShell />
</template>

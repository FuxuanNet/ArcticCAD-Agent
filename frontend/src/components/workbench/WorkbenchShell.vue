<script setup lang="ts">
import { ref } from "vue"
import {
  ResizableHandle,
  ResizablePanel,
  ResizablePanelGroup,
} from "@/components/ui/resizable"
import AgentChatSheet from "./AgentChatSheet.vue"
import AssetImportDialog from "./AssetImportDialog.vue"
import CanvasPreview from "./CanvasPreview.vue"
import InspectorPanel from "./InspectorPanel.vue"
import ReviewDialog from "./ReviewDialog.vue"
import WorkbenchSidebar from "./WorkbenchSidebar.vue"
import WorkbenchToolbar from "./WorkbenchToolbar.vue"

const chatOpen = ref(false)
const importOpen = ref(false)
const reviewOpen = ref(false)
</script>

<template>
  <main class="flex h-screen min-h-[640px] overflow-hidden bg-background text-foreground">
    <WorkbenchSidebar />
    <section class="flex min-w-0 flex-1 flex-col">
      <WorkbenchToolbar
        :on-open-chat="() => (chatOpen = true)"
        :on-open-import="() => (importOpen = true)"
        :on-open-review="() => (reviewOpen = true)"
      />
      <ResizablePanelGroup direction="horizontal" class="min-h-0 flex-1">
        <ResizablePanel :default-size="62" :min-size="42">
          <CanvasPreview />
        </ResizablePanel>
        <ResizableHandle with-handle />
        <ResizablePanel :default-size="38" :min-size="28" class="min-w-[420px]">
          <InspectorPanel />
        </ResizablePanel>
      </ResizablePanelGroup>
    </section>
    <AgentChatSheet v-model:open="chatOpen" />
    <AssetImportDialog v-model:open="importOpen" />
    <ReviewDialog v-model:open="reviewOpen" />
  </main>
</template>

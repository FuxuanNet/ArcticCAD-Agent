<script setup lang="ts">
import { ref } from "vue"
import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { Textarea } from "@/components/ui/textarea"
import { useWorkbenchStore } from "@/stores/workbench"
import { Camera, Loader2, ScanSearch } from "lucide-vue-next"

const open = defineModel<boolean>("open", { default: false })
const store = useWorkbenchStore()
const isCapturing = ref(false)

async function capture() {
  isCapturing.value = true
  try {
    await store.stageReviewSnapshot()
  } finally {
    isCapturing.value = false
  }
}

async function submitReview() {
  await store.requestReview()
  open.value = false
}

function snapshotSizeText() {
  const size = store.stagedReviewSnapshotMeta?.byteSize || 0
  if (!size) return "未暂存"
  return `${Math.round(size / 1024)} KB`
}
</script>

<template>
  <Dialog v-model:open="open">
    <DialogContent class="sm:max-w-[620px]">
      <DialogHeader>
        <DialogTitle>截图审图</DialogTitle>
        <DialogDescription>调整画布视角后截图，再发送提示词给视觉模型。</DialogDescription>
      </DialogHeader>
      <div class="flex flex-col gap-3">
        <div class="flex items-center justify-between gap-2 rounded-md border border-border px-3 py-2 text-sm">
          <div class="min-w-0">
            <div class="truncate text-sm">{{ store.stagedReviewSnapshotBase64 ? "将发送暂存截图" : "尚未暂存截图" }}</div>
            <div class="truncate text-xs text-muted-foreground">
              {{ store.stagedReviewSnapshotMeta ? `${snapshotSizeText()} · ${new Date(store.stagedReviewSnapshotMeta.capturedAt).toLocaleTimeString()}` : "发送时会自动截取当前视角" }}
            </div>
          </div>
          <div class="flex items-center gap-2">
            <Button variant="outline" size="sm" :disabled="isCapturing" @click="capture">
              <Loader2 v-if="isCapturing" data-icon="inline-start" class="animate-spin" />
              <Camera v-else data-icon="inline-start" />
              截图
            </Button>
            <Button variant="ghost" size="sm" :disabled="!store.stagedReviewSnapshotBase64" @click="store.clearStagedReviewSnapshot">
              清除
            </Button>
          </div>
        </div>
        <Textarea v-model="store.reviewPrompt" class="min-h-28" />
      </div>
      <DialogFooter>
        <Button variant="outline" :disabled="store.isReviewRunning" @click="store.clearReviewSnapshots">
          清理审图截图
        </Button>
        <Button :disabled="store.isReviewRunning || !store.currentVersionId" @click="submitReview">
          <Loader2 v-if="store.isReviewRunning" data-icon="inline-start" class="animate-spin" />
          <ScanSearch v-else data-icon="inline-start" />
          发送审图
        </Button>
      </DialogFooter>
    </DialogContent>
  </Dialog>
</template>

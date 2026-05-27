<script setup lang="ts">
import { computed, ref } from "vue"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Badge } from "@/components/ui/badge"
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
import { AlertTriangle, FileUp, Loader2, Wand2 } from "lucide-vue-next"

const open = defineModel<boolean>("open", { default: false })
const store = useWorkbenchStore()
const fileInput = ref<HTMLInputElement | null>(null)
const pickedFile = ref<File | null>(null)

const selectedAsset = computed(() => store.selectedAssetDetail?.asset)
const summary = computed(() => store.selectedAssetSummary)
const entitySummary = computed(() => {
  const counts = summary.value?.entityCounts || {}
  const entries = Object.entries(counts)
  if (entries.length) {
    return entries.map(([name, count]) => `${name} ${count}`).join(" · ")
  }
  if (summary.value?.format === "stl") {
    return `${summary.value.triangleCount || 0} triangles · ${summary.value.solidCount || 0} solids`
  }
  return "等待摘要"
})

async function uploadPickedFile() {
  if (!pickedFile.value) return
  const detail = await store.uploadAsset(pickedFile.value)
  if (detail) {
    pickedFile.value = null
    if (fileInput.value) fileInput.value.value = ""
  }
}

function onFileChange(event: Event) {
  pickedFile.value = (event.target as HTMLInputElement).files?.[0] || null
}
</script>

<template>
  <Dialog v-model:open="open">
    <DialogContent class="sm:max-w-[640px]">
      <DialogHeader>
        <DialogTitle>导入 CAD / 模型资产</DialogTitle>
        <DialogDescription>支持 DXF 语义重建和 STL 参考模型。</DialogDescription>
      </DialogHeader>

      <div class="flex flex-col gap-4">
        <div class="flex items-center gap-2">
          <input ref="fileInput" type="file" accept=".dxf,.stl" class="min-w-0 flex-1 text-sm" @change="onFileChange" />
          <Button :disabled="!pickedFile || store.isAssetUploading" @click="uploadPickedFile">
            <Loader2 v-if="store.isAssetUploading" data-icon="inline-start" class="animate-spin" />
            <FileUp v-else data-icon="inline-start" />
            导入
          </Button>
        </div>

        <Alert v-if="store.assetError" variant="destructive" class="rounded-md">
          <AlertTriangle />
          <AlertTitle>资产处理失败</AlertTitle>
          <AlertDescription>{{ store.assetError }}</AlertDescription>
        </Alert>

        <div v-if="selectedAsset" class="flex flex-col gap-3 rounded-md border border-border p-3">
          <div class="flex items-center justify-between gap-2">
            <div class="min-w-0">
              <div class="truncate text-sm font-medium">{{ selectedAsset.filename }}</div>
              <div class="truncate text-xs text-muted-foreground">{{ entitySummary }}</div>
            </div>
            <div class="flex items-center gap-2">
              <Badge variant="outline">{{ selectedAsset.format.toUpperCase() }}</Badge>
              <Badge variant="secondary">{{ selectedAsset.status }}</Badge>
            </div>
          </div>
          <div v-if="summary?.warnings?.length" class="text-xs leading-5 text-muted-foreground">
            {{ summary.warnings[0] }}
          </div>
          <Textarea
            v-model="store.assetRebuildPrompt"
            class="min-h-20"
            placeholder="描述希望 AI 如何根据该资产重建，例如：识别闭合墙体轮廓并拉伸为 3D 临建平面。"
          />
        </div>
      </div>

      <DialogFooter>
        <Button
          variant="outline"
          :disabled="!selectedAsset || selectedAsset.format === 'stl' || store.isAgentRunning"
          @click="store.reconstructSelectedAsset('direct_insert')"
        >
          直接插入几何资产
        </Button>
        <Button :disabled="!selectedAsset || store.isAgentRunning" @click="store.reconstructSelectedAsset('reference_rebuild')">
          <Loader2 v-if="store.isAssetRebuilding" data-icon="inline-start" class="animate-spin" />
          <Wand2 v-else data-icon="inline-start" />
          作为参考重建
        </Button>
      </DialogFooter>
    </DialogContent>
  </Dialog>
</template>

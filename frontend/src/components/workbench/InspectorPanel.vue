<script setup lang="ts">
import { VueMonacoEditor } from "@guolao/vue-monaco-editor"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { ScrollArea } from "@/components/ui/scroll-area"
import { Separator } from "@/components/ui/separator"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { useWorkbenchStore } from "@/stores/workbench"
import { AlertTriangle, CircleCheck, FileCode2, ListChecks, ScrollText } from "lucide-vue-next"

const store = useWorkbenchStore()

const editorOptions = {
  automaticLayout: true,
  minimap: { enabled: false },
  fontSize: 12,
  lineNumbersMinChars: 3,
  scrollBeyondLastLine: false,
  wordWrap: "on" as const,
  tabSize: 2,
}
</script>

<template>
  <Tabs v-model="store.inspectorTab" class="flex h-full min-h-0 flex-col">
    <div class="flex h-10 items-center justify-between border-b border-border px-2">
      <TabsList class="h-8">
        <TabsTrigger value="code" class="text-xs">
          <FileCode2 data-icon="inline-start" />
          代码
        </TabsTrigger>
        <TabsTrigger value="review" class="text-xs">
          <ListChecks data-icon="inline-start" />
          审图
          <span v-if="store.isReviewRunning" class="ml-1 size-1.5 rounded-full bg-primary" />
        </TabsTrigger>
        <TabsTrigger value="logs" class="text-xs">
          <ScrollText data-icon="inline-start" />
          日志
        </TabsTrigger>
      </TabsList>
      <Badge variant="outline">{{ store.currentVersion?.status || "draft" }}</Badge>
    </div>

    <TabsContent value="code" class="m-0 min-h-0 flex-1">
      <div v-if="!store.currentVersionId" class="flex h-full min-h-[420px] items-center justify-center p-4 text-sm text-muted-foreground">
        当前项目为空。请在对话中描述建模需求，由真实 AI 生成首个 JSCAD 版本。
      </div>
      <VueMonacoEditor
        v-else
        v-model:value="store.code"
        language="javascript"
        theme="vs-dark"
        class="h-full min-h-[420px]"
        :options="editorOptions"
      />
    </TabsContent>

    <TabsContent value="review" class="m-0 min-h-0 flex-1">
      <ScrollArea class="h-full">
        <div class="flex flex-col gap-3 p-3">
          <Alert v-if="store.reviewError" variant="destructive" class="rounded-md">
            <AlertTriangle />
            <AlertTitle>审图失败</AlertTitle>
            <AlertDescription>{{ store.reviewError }}</AlertDescription>
          </Alert>
          <Alert class="rounded-md">
            <CircleCheck />
            <AlertTitle>审图摘要</AlertTitle>
            <AlertDescription>{{ store.isReviewRunning ? "正在调用视觉模型审查当前画布。" : store.currentReview?.summary || "暂无审图报告。" }}</AlertDescription>
          </Alert>
          <div class="grid gap-2">
            <div
              v-for="risk in store.currentReview?.risks || []"
              :key="risk.category"
              class="rounded-md border border-border p-3 text-sm"
            >
              <div class="mb-2 flex items-center justify-between gap-2">
                <span class="font-medium">{{ risk.category }}</span>
                <Badge :variant="risk.level === 'high' ? 'destructive' : 'secondary'">{{ risk.level }}</Badge>
              </div>
              <p class="leading-5 text-muted-foreground">{{ risk.description }}</p>
              <Separator class="my-2" />
              <p class="leading-5">{{ risk.suggestion }}</p>
            </div>
          </div>
          <div v-if="store.currentReview?.observations?.length" class="grid gap-2">
            <div class="text-xs font-medium text-muted-foreground">图像观察</div>
            <div
              v-for="item in store.currentReview.observations"
              :key="item"
              class="rounded-md border border-border px-3 py-2 text-sm leading-5"
            >
              {{ item }}
            </div>
          </div>
          <div v-if="store.currentReview?.suggestedFixes?.length" class="grid gap-2">
            <div class="text-xs font-medium text-muted-foreground">建议修改</div>
            <div
              v-for="item in store.currentReview.suggestedFixes"
              :key="item"
              class="grid gap-2 rounded-md border border-border px-3 py-2 text-sm leading-5"
            >
              <span>{{ item }}</span>
              <Button size="sm" variant="outline" :disabled="store.isAgentRunning" @click="store.applyReviewSuggestion(item)">
                应用建议
              </Button>
            </div>
          </div>
          <div v-if="store.currentReview?.evidence?.length" class="grid gap-2">
            <div class="text-xs font-medium text-muted-foreground">依据</div>
            <div
              v-for="item in store.currentReview.evidence"
              :key="item"
              class="rounded-md border border-border px-3 py-2 text-xs leading-5 text-muted-foreground"
            >
              {{ item }}
            </div>
          </div>
          <div v-if="store.runs.length" class="grid gap-2">
            <div class="text-xs font-medium text-muted-foreground">运行历史</div>
            <div
              v-for="run in store.runs.slice(0, 6)"
              :key="`${run.versionId}-${run.createdAt}`"
              class="grid grid-cols-[1fr_auto] gap-2 rounded-md border border-border px-3 py-2 text-xs"
            >
              <span class="truncate">{{ run.versionId }}</span>
              <Badge :variant="run.ok ? 'secondary' : 'outline'">
                {{ run.ok ? "ok" : run.error?.kind || "error" }}
              </Badge>
              <span class="col-span-2 text-muted-foreground">
                {{ new Date(run.createdAt).toLocaleString() }} · repair #{{ run.autoRepairAttempt }}
              </span>
            </div>
          </div>
        </div>
      </ScrollArea>
    </TabsContent>

    <TabsContent value="logs" class="m-0 min-h-0 flex-1">
      <ScrollArea class="h-full">
        <div class="flex flex-col gap-2 p-3">
          <Alert v-if="store.lastRunResult?.error" variant="destructive" class="rounded-md">
            <AlertTriangle />
            <AlertTitle>{{ store.lastRunResult.error.kind }} error</AlertTitle>
            <AlertDescription>{{ store.lastRunResult.error.message }}</AlertDescription>
          </Alert>
          <div
            v-for="event in store.events"
            :key="event.id"
            class="grid gap-1 rounded-md border border-border p-2 text-xs"
          >
            <div class="flex items-center justify-between gap-2">
              <Badge variant="outline">{{ event.type }}</Badge>
              <span class="text-muted-foreground">{{ new Date(event.createdAt).toLocaleTimeString() }}</span>
            </div>
            <p class="leading-5 text-muted-foreground">
              {{ "message" in event && event.message ? event.message : "summary" in event ? event.summary : event.type }}
            </p>
          </div>
        </div>
      </ScrollArea>
    </TabsContent>
  </Tabs>
</template>

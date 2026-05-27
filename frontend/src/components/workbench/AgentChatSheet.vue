<script setup lang="ts">
import { ref, watch } from "vue"
import { Button } from "@/components/ui/button"
import { ScrollArea } from "@/components/ui/scroll-area"
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet"
import { Textarea } from "@/components/ui/textarea"
import { useWorkbenchStore } from "@/stores/workbench"
import type { AgentEvent } from "@/types/domain"
import { BrainCircuit, ChevronDown, SendHorizontal, StopCircle } from "lucide-vue-next"

defineProps<{
  open: boolean
}>()

const emit = defineEmits<{
  "update:open": [value: boolean]
}>()

const store = useWorkbenchStore()
const draft = ref("")
const knownEventIds = ref<Set<string>>(new Set())
const expandedThinkingIds = ref<Set<string>>(new Set())
const manuallyToggledThinkingIds = ref<Set<string>>(new Set())

async function submit() {
  const content = draft.value
  draft.value = ""
  await store.sendMessage(content)
}

function eventMessage(event: AgentEvent) {
  if ("message" in event && event.message) {
    return event.message
  }
  if ("summary" in event) {
    return event.summary
  }
  if ("reason" in event) {
    return event.reason
  }
  return event.type
}

function isThinkingOpen(event: AgentEvent) {
  if (event.type !== "thinking") {
    return false
  }
  return store.isAgentRunning
    ? expandedThinkingIds.value.has(event.id)
    : manuallyToggledThinkingIds.value.has(event.id) && expandedThinkingIds.value.has(event.id)
}

function toggleThinking(event: AgentEvent) {
  if (event.type !== "thinking") {
    return
  }
  const nextExpanded = new Set(expandedThinkingIds.value)
  const nextManual = new Set(manuallyToggledThinkingIds.value)
  nextManual.add(event.id)
  if (isThinkingOpen(event)) {
    nextExpanded.delete(event.id)
  } else {
    nextExpanded.add(event.id)
  }
  expandedThinkingIds.value = nextExpanded
  manuallyToggledThinkingIds.value = nextManual
}

watch(
  () => store.events.map((event) => `${event.id}:${event.type}`).join("|"),
  () => {
    const events = store.events
    const known = new Set(knownEventIds.value)
    let expanded = new Set(expandedThinkingIds.value)
    let manual = new Set(manuallyToggledThinkingIds.value)

    for (const event of [...events].reverse()) {
      if (known.has(event.id)) {
        continue
      }
      known.add(event.id)
      if (event.type === "thinking") {
        expanded.add(event.id)
      }
      if (event.type === "done") {
        expanded = new Set([...expanded].filter((id) => manual.has(id)))
      }
    }

    const currentIds = new Set(events.map((event) => event.id))
    expanded = new Set([...expanded].filter((id) => currentIds.has(id)))
    manual = new Set([...manual].filter((id) => currentIds.has(id)))
    knownEventIds.value = new Set([...known].filter((id) => currentIds.has(id)))
    expandedThinkingIds.value = expanded
    manuallyToggledThinkingIds.value = manual
  },
)
</script>

<template>
  <Sheet :open="open" @update:open="emit('update:open', $event)">
    <SheetContent side="right" class="flex w-[440px] flex-col gap-0 p-0 sm:max-w-[440px]">
      <SheetHeader class="border-b border-border px-4 py-3">
        <SheetTitle>项目对话</SheetTitle>
        <SheetDescription>消息、事件流和工具调用摘要</SheetDescription>
      </SheetHeader>

      <ScrollArea class="min-h-0 flex-1">
        <div class="flex flex-col gap-3 p-3">
          <div
            v-for="message in store.conversationMessages"
            :key="message.id"
            class="rounded-md border border-border p-3 text-sm"
            :class="{ 'bg-muted': message.role === 'user' }"
          >
            <div class="mb-1 text-xs text-muted-foreground">{{ message.role }}</div>
            <p class="leading-5">{{ message.content }}</p>
          </div>
          <div
            v-for="event in store.events.slice(0, 30)"
            :key="event.id"
            class="rounded-md border border-border bg-card text-xs"
          >
            <template v-if="event.type === 'thinking'">
              <button
                type="button"
                class="flex w-full items-center gap-2 px-2 py-2 text-left font-medium"
                :aria-expanded="isThinkingOpen(event)"
                @click="toggleThinking(event)"
              >
                <BrainCircuit class="size-4 text-muted-foreground" />
                <span class="min-w-0 flex-1">模型思考</span>
                <span class="text-[11px] font-normal text-muted-foreground">
                  {{ isThinkingOpen(event) ? "展开中" : "已折叠" }}
                </span>
                <ChevronDown
                  class="size-4 text-muted-foreground transition-transform"
                  :class="{ '-rotate-90': !isThinkingOpen(event) }"
                />
              </button>
              <p
                v-if="isThinkingOpen(event)"
                class="border-t border-border px-2 py-2 leading-5 whitespace-pre-wrap text-muted-foreground"
              >
                {{ event.message }}
              </p>
            </template>
            <template v-else>
              <div class="px-2 pt-2 font-medium">{{ event.type }}</div>
              <p class="px-2 pb-2 pt-1 leading-5 text-muted-foreground">
                {{ eventMessage(event) }}
              </p>
            </template>
          </div>
        </div>
      </ScrollArea>

      <form class="grid gap-2 border-t border-border p-3" @submit.prevent="submit">
        <Textarea
          v-model="draft"
          class="min-h-20 resize-none rounded-md text-sm"
          placeholder="描述绘图、改图或审图需求"
          :disabled="store.isAgentRunning"
        />
        <Button type="submit" :disabled="store.isAgentRunning || !draft.trim()">
          <SendHorizontal data-icon="inline-start" />
          发送
        </Button>
        <Button v-if="store.canStopAgent" type="button" variant="outline" @click="store.stopActiveAgent">
          <StopCircle data-icon="inline-start" />
          停止本次对话
        </Button>
      </form>
    </SheetContent>
  </Sheet>
</template>

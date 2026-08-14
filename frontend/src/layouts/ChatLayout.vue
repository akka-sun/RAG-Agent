<script setup lang="ts">
import { nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'

const props = defineProps<{ railOpen: boolean }>()
const emit = defineEmits<{ closeRail: [] }>()
const rail = ref<HTMLElement | null>(null)
const overlayMode = ref(false)
let mediaQuery: MediaQueryList | null = null
let previousFocus: HTMLElement | null = null

const focusableSelector = 'button:not([disabled]), [href], input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])'

function focusableRailElements(): HTMLElement[] {
  return rail.value ? Array.from(rail.value.querySelectorAll<HTMLElement>(focusableSelector)) : []
}

function updateOverlayMode(event: MediaQueryListEvent | MediaQueryList): void {
  overlayMode.value = event.matches
}

function keydown(event: KeyboardEvent): void {
  if (!overlayMode.value || !props.railOpen) return
  if (event.key === 'Escape') {
    event.preventDefault()
    emit('closeRail')
    return
  }
  if (event.key !== 'Tab') return
  const elements = focusableRailElements()
  if (!elements.length) return
  const first = elements[0]
  const last = elements[elements.length - 1]
  if (event.shiftKey && document.activeElement === first) {
    event.preventDefault()
    last.focus()
  } else if (!event.shiftKey && document.activeElement === last) {
    event.preventDefault()
    first.focus()
  }
}

watch(() => props.railOpen, async (open) => {
  if (!overlayMode.value) return
  if (open) {
    previousFocus = document.activeElement instanceof HTMLElement ? document.activeElement : null
    await nextTick()
    focusableRailElements()[0]?.focus()
  } else {
    await nextTick()
    previousFocus?.focus()
  }
})

onMounted(() => {
  if (typeof window.matchMedia !== 'function') return
  mediaQuery = window.matchMedia('(max-width: 64rem)')
  updateOverlayMode(mediaQuery)
  mediaQuery.addEventListener('change', updateOverlayMode)
})
onBeforeUnmount(() => mediaQuery?.removeEventListener('change', updateOverlayMode))
</script>

<template>
  <div class="chat-layout" :class="{ 'chat-layout--rail-open': railOpen }">
    <button v-if="railOpen" type="button" tabindex="-1" class="chat-layout__backdrop" aria-label="关闭会话历史" @click="$emit('closeRail')" />
    <aside
      id="conversation-history"
      ref="rail"
      class="chat-layout__conversation-rail"
      aria-label="会话历史"
      :aria-hidden="overlayMode && !railOpen ? 'true' : undefined"
      :inert="overlayMode && !railOpen ? true : undefined"
      @keydown="keydown"
    >
      <slot name="rail" />
    </aside>
    <section class="chat-layout__main" aria-label="当前对话" :inert="overlayMode && railOpen ? true : undefined">
      <slot />
    </section>
  </div>
</template>

<script setup lang="ts">
import { nextTick, onBeforeUnmount, ref, watch } from 'vue'

const props = defineProps<{
  open: boolean
  ariaLabel?: string
  ariaLabelledby?: string
  initialFocus?: string
}>()

const emit = defineEmits<{ close: [] }>()
const root = ref<HTMLElement | null>(null)
const panel = ref<HTMLElement | null>(null)
let previousFocus: HTMLElement | null = null
let inertBackground = new Map<HTMLElement, boolean>()

const focusableSelector = [
  'button:not([disabled])',
  '[href]',
  'input:not([disabled])',
  'select:not([disabled])',
  'textarea:not([disabled])',
  '[tabindex]:not([tabindex="-1"])',
].join(', ')

function focusableElements(): HTMLElement[] {
  return panel.value ? Array.from(panel.value.querySelectorAll<HTMLElement>(focusableSelector)) : []
}

function isolateBackground(): void {
  restoreBackground()
  let current = root.value
  while (current?.parentElement) {
    const parent = current.parentElement
    for (const sibling of Array.from(parent.children)) {
      if (!(sibling instanceof HTMLElement) || sibling === current || inertBackground.has(sibling)) continue
      inertBackground.set(sibling, sibling.hasAttribute('inert'))
      sibling.setAttribute('inert', '')
    }
    if (parent === document.body) break
    current = parent
  }
}

function restoreBackground(): void {
  for (const [element, wasInert] of inertBackground) {
    if (!wasInert) element.removeAttribute('inert')
  }
  inertBackground = new Map()
}

async function focusInitialElement(): Promise<void> {
  await nextTick()
  isolateBackground()
  const preferred = props.initialFocus ? panel.value?.querySelector<HTMLElement>(props.initialFocus) : null
  ;(preferred ?? focusableElements()[0] ?? panel.value)?.focus()
}

async function restoreFocus(): Promise<void> {
  await nextTick()
  previousFocus?.focus()
  previousFocus = null
}

function keydown(event: KeyboardEvent): void {
  if (event.key === 'Escape') {
    event.preventDefault()
    emit('close')
    return
  }
  if (event.key !== 'Tab') return
  const elements = focusableElements()
  if (elements.length === 0) {
    event.preventDefault()
    panel.value?.focus()
    return
  }
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

watch(() => props.open, async (open) => {
  if (open) {
    previousFocus = document.activeElement instanceof HTMLElement ? document.activeElement : null
    await focusInitialElement()
  } else {
    restoreBackground()
    await restoreFocus()
  }
}, { immediate: true })

onBeforeUnmount(() => {
  restoreBackground()
  previousFocus?.focus()
})
</script>

<template>
  <div v-if="open" ref="root" class="modal-dialog" role="presentation">
    <section
      ref="panel"
      class="modal-dialog__panel"
      role="dialog"
      aria-modal="true"
      :aria-label="ariaLabel"
      :aria-labelledby="ariaLabelledby"
      tabindex="-1"
      @keydown="keydown"
    >
      <slot />
    </section>
  </div>
</template>

<style scoped>
.modal-dialog {
  position: fixed;
  z-index: 20;
  inset: 0;
  display: grid;
  place-items: center;
  padding: 1rem;
  background: rgb(23 26 43 / 45%);
}

.modal-dialog__panel {
  width: min(100%, 28rem);
  max-height: calc(100vh - 2rem);
  padding: 1.5rem;
  overflow-y: auto;
  border-radius: 0.75rem;
  background: var(--color-surface);
  box-shadow: var(--shadow-surface);
}
</style>

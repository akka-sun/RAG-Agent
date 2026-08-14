<script setup lang="ts">
import { nextTick, onBeforeUnmount, onMounted, ref } from 'vue'
import AppSidebar from '@/components/navigation/AppSidebar.vue'
import { useKnowledgeBaseStore } from '@/stores/knowledge-bases'

const knowledgeBases = useKnowledgeBaseStore()
const navOpen = ref(false)
const mobileMode = ref(false)
const shell = ref<HTMLElement | null>(null)
const navToggle = ref<HTMLButtonElement | null>(null)
let mediaQuery: MediaQueryList | null = null

const focusableSelector = 'button:not([disabled]), [href], input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])'

function navigation(): HTMLElement | null {
  return shell.value?.querySelector<HTMLElement>('#global-navigation') ?? null
}

function navigationItems(): HTMLElement[] {
  const element = navigation()
  return element ? Array.from(element.querySelectorAll<HTMLElement>(focusableSelector)) : []
}

function updateMobileMode(event: MediaQueryListEvent | MediaQueryList): void {
  mobileMode.value = event.matches
  if (!event.matches) navOpen.value = false
}

async function toggleNavigation(): Promise<void> {
  navOpen.value = !navOpen.value
  if (navOpen.value && mobileMode.value) {
    await nextTick()
    navigationItems()[0]?.focus()
  }
}

async function closeNavigation(): Promise<void> {
  navOpen.value = false
  if (mobileMode.value) {
    await nextTick()
    navToggle.value?.focus()
  }
}

function navigationKeydown(event: KeyboardEvent): void {
  if (!mobileMode.value || !navOpen.value) return
  if (event.key === 'Escape') {
    event.preventDefault()
    void closeNavigation()
    return
  }
  if (event.key !== 'Tab') return
  const elements = navigationItems()
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

onMounted(() => {
  if (typeof window.matchMedia === 'function') {
    mediaQuery = window.matchMedia('(max-width: 44rem)')
    updateMobileMode(mediaQuery)
    mediaQuery.addEventListener('change', updateMobileMode)
  }
  void knowledgeBases.load()
})
onBeforeUnmount(() => mediaQuery?.removeEventListener('change', updateMobileMode))
</script>

<template>
  <div ref="shell" class="app-shell">
    <button
      ref="navToggle"
      type="button"
      class="app-shell__nav-toggle"
      aria-controls="global-navigation"
      :aria-expanded="navOpen"
      aria-label="打开主导航"
      @click="toggleNavigation"
    >☰</button>
    <button v-if="navOpen" type="button" tabindex="-1" class="app-shell__nav-backdrop" aria-label="关闭主导航" @click="closeNavigation" />
    <AppSidebar
      id="global-navigation"
      :class="{ 'app-sidebar--open': navOpen }"
      :aria-hidden="mobileMode && !navOpen ? 'true' : undefined"
      :inert="mobileMode && !navOpen ? true : undefined"
      :selected-knowledge-base-id="knowledgeBases.selectedId ?? undefined"
      @click="closeNavigation"
      @keydown="navigationKeydown"
    />
    <main class="app-shell__content" tabindex="-1" :inert="mobileMode && navOpen ? true : undefined">
      <router-view />
    </main>
  </div>
</template>

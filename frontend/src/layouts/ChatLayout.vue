<script setup lang="ts">
defineProps<{ railOpen: boolean }>()
defineEmits<{ closeRail: [] }>()
</script>

<template>
  <div class="chat-layout" :class="{ 'chat-layout--rail-open': railOpen }">
    <button v-if="railOpen" type="button" class="chat-layout__backdrop" aria-label="关闭会话历史" @click="$emit('closeRail')" />
    <aside class="chat-layout__conversation-rail" aria-label="会话历史">
      <slot name="rail" />
    </aside>
    <section class="chat-layout__main" aria-label="当前对话">
      <slot />
    </section>
  </div>
</template>

<script setup lang="ts">
import type { TrackedIngestionTask } from '@/stores/documents'

defineProps<{ tasks: TrackedIngestionTask[] }>()

const statusLabels = {
  pending: '等待处理',
  processing: '处理中',
  completed: '处理完成',
  failed: '处理失败',
} as const
</script>

<template>
  <section v-if="tasks.length" class="ingestion-progress" aria-labelledby="ingestion-progress-title">
    <h2 id="ingestion-progress-title">摄取任务</h2>
    <article v-for="tracked in tasks" :key="tracked.taskId" class="ingestion-progress__item">
      <div class="ingestion-progress__heading">
        <strong>文档 {{ tracked.documentId }}</strong>
        <span>{{ tracked.task ? statusLabels[tracked.task.status] : '等待状态更新' }}</span>
      </div>
      <template v-if="tracked.task">
        <p>阶段：{{ tracked.task.stage }}</p>
        <div class="ingestion-progress__meter" role="progressbar" aria-label="摄取进度" aria-valuemin="0" aria-valuemax="100" :aria-valuenow="tracked.task.progress">
          <span :style="{ width: `${tracked.task.progress}%` }" />
        </div>
        <p>{{ tracked.task.progress }}%</p>
        <p v-if="tracked.task.error" class="ingestion-progress__error">{{ tracked.task.error }}</p>
      </template>
      <p v-if="tracked.pollingError" class="ingestion-progress__error" role="alert">{{ tracked.pollingError }}</p>
    </article>
  </section>
</template>

<style scoped>
.ingestion-progress { display: grid; gap: 0.75rem; }
.ingestion-progress h2, .ingestion-progress p { margin: 0; }
.ingestion-progress__item { display: grid; gap: 0.5rem; padding: 1rem; border: 1px solid var(--color-border); border-radius: 0.75rem; background: var(--color-page); }
.ingestion-progress__heading { display: flex; justify-content: space-between; gap: 1rem; }
.ingestion-progress__heading span, .ingestion-progress p { color: var(--color-text-muted); font-size: 0.875rem; }
.ingestion-progress__meter { overflow: hidden; height: 0.5rem; border-radius: 999px; background: var(--color-border); }
.ingestion-progress__meter span { display: block; height: 100%; border-radius: inherit; background: var(--color-action); }
.ingestion-progress .ingestion-progress__error { color: var(--color-destructive); }
</style>

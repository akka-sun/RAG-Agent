<script setup lang="ts">
import { reactive } from 'vue'
import type { KnowledgeBaseCreate } from '@/types/api'

const emit = defineEmits<{
  submit: [input: KnowledgeBaseCreate]
  cancel: []
}>()

const form = reactive({
  name: '',
  description: '',
  embeddingModel: '',
  embeddingDimension: '',
})

const errors = reactive({
  name: '',
  embeddingModel: '',
  embeddingDimension: '',
})

function validate(): boolean {
  errors.name = form.name.trim() ? '' : '知识库名称不能为空'
  errors.embeddingModel = form.embeddingModel.trim() ? '' : '嵌入模型不能为空'
  const dimension = Number(form.embeddingDimension)
  errors.embeddingDimension = Number.isInteger(dimension) && dimension > 0 ? '' : '维度必须是正整数'
  return !errors.name && !errors.embeddingModel && !errors.embeddingDimension
}

function submit(): void {
  if (!validate()) return

  emit('submit', {
    name: form.name.trim(),
    description: form.description,
    embedding_model: form.embeddingModel.trim(),
    embedding_dimension: Number(form.embeddingDimension),
  })
}
</script>

<template>
  <form class="knowledge-base-form" novalidate @submit.prevent="submit">
    <label for="knowledge-base-name">知识库名称</label>
    <input id="knowledge-base-name" v-model="form.name" type="text" maxlength="200" required>
    <p v-if="errors.name" class="field-error">{{ errors.name }}</p>

    <label for="knowledge-base-description">描述（可选）</label>
    <textarea id="knowledge-base-description" v-model="form.description" rows="3" />

    <label for="knowledge-base-model">嵌入模型</label>
    <input id="knowledge-base-model" v-model="form.embeddingModel" type="text" maxlength="200" required>
    <p v-if="errors.embeddingModel" class="field-error">{{ errors.embeddingModel }}</p>

    <label for="knowledge-base-dimension">向量维度</label>
    <input id="knowledge-base-dimension" v-model="form.embeddingDimension" type="number" min="1" step="1" required>
    <p v-if="errors.embeddingDimension" class="field-error">{{ errors.embeddingDimension }}</p>

    <div class="knowledge-base-form__actions">
      <button type="button" class="button button--secondary" @click="emit('cancel')">取消</button>
      <button type="submit" class="button">创建知识库</button>
    </div>
  </form>
</template>

<style scoped>
.knowledge-base-form {
  display: grid;
  gap: 0.5rem;
}

.knowledge-base-form input,
.knowledge-base-form textarea {
  width: 100%;
  padding: 0.625rem 0.75rem;
  border: 1px solid var(--color-border);
  border-radius: 0.5rem;
  color: var(--color-text);
  font: inherit;
}

.field-error {
  margin: 0;
  color: var(--color-destructive);
  font-size: 0.875rem;
}

.knowledge-base-form__actions {
  display: flex;
  justify-content: flex-end;
  gap: 0.75rem;
  margin-top: 0.75rem;
}
</style>

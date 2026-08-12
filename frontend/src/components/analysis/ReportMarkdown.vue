<script setup lang="ts">
import DOMPurify from 'dompurify'
import { marked } from 'marked'
import { computed } from 'vue'
const props = defineProps<{ markdown: string }>()
const html = computed(() => DOMPurify.sanitize(marked.parse(props.markdown, { async: false }) as string))
</script>

<template><section class="report-markdown" v-html="html" /></template>

<style scoped>
.report-markdown { margin: 16px 0; padding: 4px 0; line-height: 1.7; }
.report-markdown :deep(h1), .report-markdown :deep(h2), .report-markdown :deep(h3) { margin: 16px 0 8px; }
.report-markdown :deep(table) { width: 100%; border-collapse: collapse; }
.report-markdown :deep(th), .report-markdown :deep(td) { padding: 6px 8px; border-bottom: 1px solid #eee; text-align: left; }
</style>

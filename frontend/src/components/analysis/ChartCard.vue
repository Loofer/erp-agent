<script setup lang="ts">
import { computed, h, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { DownloadOutlined } from '@ant-design/icons-vue'
import { BarChart, LineChart, PieChart } from 'echarts/charts'
import {
  GridComponent,
  LegendComponent,
  TooltipComponent,
} from 'echarts/components'
import * as echarts from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import type { EChartsCoreOption, EChartsType } from 'echarts/core'
import { chartSpecToEChartsOption } from '@/visualization/chart'
import type { ChartSpec } from '@/visualization/chart'

echarts.use([
  BarChart,
  LineChart,
  PieChart,
  GridComponent,
  LegendComponent,
  TooltipComponent,
  CanvasRenderer,
])

const props = defineProps<{ chart: ChartSpec }>()
const chartElement = ref<HTMLDivElement | null>(null)
const rendered = ref(false)
let instance: EChartsType | null = null
let resizeObserver: ResizeObserver | null = null
const renderError = ref<string | null>(null)

const rows = computed(() => props.chart.data)
const columns = computed(() => {
  const result: string[] = []
  for (const row of rows.value) for (const key of Object.keys(row)) if (!result.includes(key)) result.push(key)
  return result.slice(0, 12)
})
const option = computed(() => chartSpecToEChartsOption(props.chart))
const canRenderChart = computed(() => option.value !== null)

function render() {
  if (!chartElement.value || !canRenderChart.value) return
  try {
    instance?.dispose()
    instance = echarts.init(chartElement.value)
    instance.setOption(option.value as EChartsCoreOption, { notMerge: true })
    rendered.value = true
    renderError.value = null
  } catch (error) {
    renderError.value = error instanceof Error ? error.message : 'Chart rendering failed'
    instance?.dispose()
    instance = null
    rendered.value = false
  }
}

function exportPng() {
  if (!instance) return
  const link = document.createElement('a')
  link.href = instance.getDataURL({ type: 'png', pixelRatio: 2, backgroundColor: '#fff' })
  link.download = `${props.chart.id || 'procurement-chart'}.png`
  link.click()
}

onMounted(async () => {
  await nextTick()
  render()
  if (chartElement.value) {
    resizeObserver = new ResizeObserver(() => instance?.resize())
    resizeObserver.observe(chartElement.value)
  }
})
watch(() => props.chart, () => nextTick(render), { deep: true })
onBeforeUnmount(() => {
  resizeObserver?.disconnect()
  instance?.dispose()
})
</script>

<template>
  <section class="chart-card">
    <header class="chart-header">
      <div>
        <h3>{{ chart.title }}</h3>
        <p v-if="chart.subtitle" class="chart-subtitle">{{ chart.subtitle }}</p>
      </div>
      <div class="chart-actions">
        <a-tag>{{ chart.chart_type }}</a-tag>
        <a-button v-if="rendered" type="text" size="small" :icon="h(DownloadOutlined)" title="Export PNG" @click="exportPng" />
      </div>
    </header>
    <div v-if="canRenderChart && !renderError" ref="chartElement" class="chart-canvas" />
    <div v-else class="table-fallback">
      <a-alert v-if="renderError" type="warning" show-icon :message="renderError" />
      <table v-if="columns.length" class="data-table">
        <thead><tr><th v-for="column in columns" :key="column">{{ column }}</th></tr></thead>
        <tbody><tr v-for="(row, index) in rows" :key="index"><td v-for="column in columns" :key="column">{{ row[column] }}</td></tr></tbody>
      </table>
      <a-empty v-else description="No chart data" />
    </div>
    <footer v-if="chart.provenance.length" class="chart-footer">Sources: {{ chart.provenance.join(', ') }}</footer>
    <ul v-if="chart.warnings.length" class="chart-warnings"><li v-for="warning in chart.warnings" :key="warning">{{ warning }}</li></ul>
  </section>
</template>

<style scoped>
.chart-card { margin: 12px 0; padding: 16px; border: 1px solid #e5e7eb; border-radius: 8px; background: #fff; }
.chart-header { display: flex; justify-content: space-between; align-items: flex-start; gap: 12px; }
.chart-header h3 { margin: 0; color: #111827; font-size: 15px; }
.chart-subtitle, .chart-footer { margin: 4px 0 0; color: #6b7280; font-size: 12px; }
.chart-actions { display: flex; align-items: center; gap: 6px; }
.chart-canvas { width: 100%; height: 300px; min-height: 220px; }
.table-fallback { margin-top: 12px; overflow: auto; }
.data-table { width: 100%; border-collapse: collapse; font-size: 12px; }
.data-table th, .data-table td { padding: 7px 8px; border-bottom: 1px solid #f0f0f0; text-align: left; white-space: pre-wrap; }
.data-table th { background: #fafafa; font-weight: 600; }
.chart-warnings { margin: 8px 0 0; padding-left: 18px; color: #ad6800; font-size: 12px; }
</style>

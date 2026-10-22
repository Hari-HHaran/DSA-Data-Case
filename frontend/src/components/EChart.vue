<template>
  <VChart class="echart" :option="option" :style="{ height }" autoresize :aria-label="ariaLabel" role="img" @click="(p) => $emit('select', p)" />
</template>
<script setup>
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { BarChart, HeatmapChart, LineChart, PieChart } from 'echarts/charts'
import { GridComponent, LegendComponent, MarkAreaComponent, MarkLineComponent, TooltipComponent, VisualMapComponent, AriaComponent } from 'echarts/components'
import VChart from 'vue-echarts'
use([CanvasRenderer, BarChart, LineChart, HeatmapChart, PieChart, GridComponent, TooltipComponent, LegendComponent, VisualMapComponent,
  MarkLineComponent, MarkAreaComponent, AriaComponent])
defineProps({ option: Object, height: { type: String, default: '300px' }, ariaLabel: String })
defineEmits(['select'])
</script>
<style scoped>
.echart { width: 100%; }
</style>

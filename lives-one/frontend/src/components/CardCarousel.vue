<template>
  <section class="carousel" :aria-label="label">
    <div class="cc-head">
      <h2 class="cc-title">{{ title }}</h2>
      <div class="cc-tools">
        <slot name="link" />
        <button class="cc-btn" type="button" :disabled="atStart" aria-label="Scroll left" @click="go(-1)"><ChevronLeft :size="16" /></button>
        <button class="cc-btn" type="button" :disabled="atEnd" aria-label="Scroll right" @click="go(1)"><ChevronRight :size="16" /></button>
      </div>
    </div>
    <div ref="track" class="cc-track" tabindex="0" @scroll.passive="update" @keydown.left.prevent="go(-1)" @keydown.right.prevent="go(1)">
      <slot />
    </div>
  </section>
</template>
<script setup>
import { nextTick, onBeforeUnmount, onMounted, ref } from 'vue'
import { ChevronLeft, ChevronRight } from 'lucide-vue-next'
defineProps({ title: String, label: String })
const track = ref(null)
const atStart = ref(true)
const atEnd = ref(false)
function update() {
  const el = track.value
  if (!el) return
  atStart.value = el.scrollLeft <= 4
  atEnd.value = el.scrollLeft + el.clientWidth >= el.scrollWidth - 4
}
function go(dir) {
  const el = track.value
  if (el) el.scrollBy({ left: dir * el.clientWidth * 0.8, behavior: 'smooth' })
}
let ro
onMounted(() => { nextTick(update); ro = new ResizeObserver(update); ro.observe(track.value) })
onBeforeUnmount(() => ro?.disconnect())
</script>
<style scoped>
.cc-head { display: flex; align-items: center; justify-content: space-between; margin-bottom: .75rem; gap: .75rem; }
.cc-title { font-size: 1.05rem; margin: 0; }
.cc-tools { display: flex; align-items: center; gap: .4rem; }
.cc-btn { width: 32px; height: 32px; border-radius: 50%; border: 1px solid var(--border); background: var(--surface); color: var(--text-2);
  display: inline-flex; align-items: center; justify-content: center; box-shadow: var(--shadow-1); transition: background .15s, opacity .15s; }
.cc-btn:hover:not(:disabled) { background: var(--surface-2); }
.cc-btn:disabled { opacity: .35; cursor: default; }
.cc-track { display: grid; grid-auto-flow: column; grid-auto-columns: minmax(220px, calc((100% - 3rem) / 4)); gap: 1rem; overflow-x: auto;
  scroll-snap-type: x mandatory; scrollbar-width: none; padding: .25rem .25rem 1.25rem; margin: -.25rem -.25rem -1rem; }
.cc-track::-webkit-scrollbar { display: none; }
.cc-track > :deep(*) { scroll-snap-align: start; }
@media (max-width: 1100px) { .cc-track { grid-auto-columns: minmax(220px, calc((100% - 2rem) / 3)); } }
@media (max-width: 700px) { .cc-track { grid-auto-columns: 78%; } }
</style>

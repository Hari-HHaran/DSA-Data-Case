import { defineStore } from 'pinia'

let n = 0
export const useToast = defineStore('toast', {
  state: () => ({ items: [] }),
  actions: {
    push(message, tone = 'success', timeout = 4500) {
      const id = ++n
      this.items.push({ id, message, tone })
      setTimeout(() => this.dismiss(id), timeout)
    },
    error(err) {
      const msg = err?.problems?.length ? `${err.message} ${err.problems.join(' ')}` : err?.message || String(err)
      this.push(msg, 'error', 7000)
    },
    dismiss(id) { this.items = this.items.filter((t) => t.id !== id) },
  },
})

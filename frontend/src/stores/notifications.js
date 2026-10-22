import { defineStore } from 'pinia'
import { get, post } from '@/api/client'

export const useNotifications = defineStore('notifications', {
  state: () => ({ items: [], unread: 0, timer: null }),
  actions: {
    async refresh() {
      try {
        const r = await get('/api/notifications', { limit: 30 })
        this.items = r.items
        this.unread = r.unread
      } catch { /* ignore polling errors */ }
    },
    async markAll() {
      await post('/api/notifications/read', { ids: null })
      await this.refresh()
    },
    async markOne(id) {
      await post('/api/notifications/read', { ids: [id] })
      await this.refresh()
    },
    start() {
      this.stop()
      this.refresh()
      this.timer = setInterval(() => this.refresh(), 15000)
    },
    stop() {
      if (this.timer) clearInterval(this.timer)
      this.timer = null
    },
  },
})

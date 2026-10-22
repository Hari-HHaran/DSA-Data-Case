import { defineStore } from 'pinia'
import { get } from '@/api/client'

export const useReference = defineStore('reference', {
  state: () => ({ countries: [], entities: [], domains: [], statuses: {}, loaded: false }),
  getters: {
    countryName: (s) => (code) => s.countries.find((c) => c.code === code)?.name || code || '—',
  },
  actions: {
    async load(force = false) {
      if (this.loaded && !force) return
      const r = await get('/api/reference')
      Object.assign(this, r, { loaded: true })
    },
  },
})

import { defineStore } from 'pinia'
import { get, post, setToken, getToken } from '@/api/client'

export const useAuth = defineStore('auth', {
  state: () => ({ user: null, personas: [], demoMode: false, ready: false }),
  getters: {
    roles: (s) => s.user?.roles || [],
    isAuthed: (s) => !!s.user,
  },
  actions: {
    has(...codes) { return codes.some((c) => this.roles.includes(c)) },
    async init() {
      try {
        const p = await get('/api/auth/demo-personas')
        this.demoMode = p.demo_mode
        this.personas = p.personas
      } catch { /* backend offline handled by views */ }
      if (getToken()) {
        try { this.user = await get('/api/auth/me') } catch { setToken(null) }
      }
      this.ready = true
    },
    async login(username, password) {
      const r = await post('/api/auth/login', { username, password })
      setToken(r.access_token)
      this.user = r.user
    },
    async switchPersona(username) {
      const r = await post('/api/auth/demo-login', { username })
      setToken(r.access_token)
      this.user = r.user
    },
    logout() {
      setToken(null)
      this.user = null
    },
  },
})

// Where each persona lands after switching (keeps the demo flowing).
export function homeFor() {
  // Everyone starts on Home, which already shows only what matters for their role.
  return '/'
}

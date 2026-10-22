import axios from 'axios'

const TOKEN_KEY = 'lives_one_token'

export const api = axios.create({ baseURL: import.meta.env.VITE_API_BASE_URL || '', timeout: 30000 })

export function getToken() {
  try { return localStorage.getItem(TOKEN_KEY) } catch { return null }
}
export function setToken(token) {
  try { token ? localStorage.setItem(TOKEN_KEY, token) : localStorage.removeItem(TOKEN_KEY) } catch { /* storage unavailable */ }
}

api.interceptors.request.use((config) => {
  const t = getToken()
  if (t) config.headers.Authorization = `Bearer ${t}`
  return config
})

let onUnauthorized = null
export function setUnauthorizedHandler(fn) { onUnauthorized = fn }

api.interceptors.response.use(
  (r) => r,
  (error) => {
    const status = error.response?.status
    const body = error.response?.data || {}
    const normalised = {
      status,
      message: body.detail && typeof body.detail === 'string' ? body.detail : error.message || 'Request failed',
      problems: body.problems || [],
      body,
    }
    if (status === 401 && onUnauthorized) onUnauthorized()
    return Promise.reject(normalised)
  },
)

export const get = (url, params) => api.get(url, { params }).then((r) => r.data)
export const post = (url, data, config) => api.post(url, data, config).then((r) => r.data)
export const patch = (url, data) => api.patch(url, data).then((r) => r.data)
export const put = (url, data) => api.put(url, data).then((r) => r.data)
export const del = (url) => api.delete(url).then((r) => r.data)

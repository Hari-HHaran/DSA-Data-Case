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
// Plain-language fallback when the server sends no message of its own.
function friendly(status) {
  if (!status) return "We can't reach the server right now. Please check your connection and try again."
  if (status === 401) return 'Please sign in again.'
  if (status === 403) return "You don't have access to this."
  if (status === 404) return "We couldn't find that. It may have been removed."
  if (status >= 500) return 'Something went wrong on our side. Please try again in a moment.'
  return 'Something went wrong. Please try again.'
}
export function setUnauthorizedHandler(fn) { onUnauthorized = fn }

api.interceptors.response.use(
  (r) => r,
  (error) => {
    const status = error.response?.status
    const body = error.response?.data || {}
    const normalised = {
      status,
      message: body.detail && typeof body.detail === 'string' ? body.detail : friendly(status),
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

import { createApp } from 'vue'
import { createPinia } from 'pinia'
import 'bootstrap/dist/css/bootstrap.min.css'
import './styles/app.css'
import App from './App.vue'
import router from './router'
import { setUnauthorizedHandler } from './api/client'
import { useAuth } from './stores/auth'

const app = createApp(App)
const pinia = createPinia()
app.use(pinia).use(router)
setUnauthorizedHandler(() => {
  const auth = useAuth()
  auth.logout()
  if (router.currentRoute.value.name !== 'login') router.push({ name: 'login' })
})
app.mount('#app')

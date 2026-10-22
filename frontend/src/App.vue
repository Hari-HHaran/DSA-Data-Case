<template>
  <AppShell v-if="auth.isAuthed && !$route.meta.public">
    <RouterView v-slot="{ Component }">
      <Transition name="fade" mode="out-in"><component :is="Component" :key="$route.path + '|' + auth.user?.id" /></Transition>
    </RouterView>
  </AppShell>
  <RouterView v-else />
  <ToastHost />
</template>

<script setup>
import AppShell from '@/components/AppShell.vue'
import ToastHost from '@/components/ToastHost.vue'
import { useAuth } from '@/stores/auth'
const auth = useAuth()
</script>

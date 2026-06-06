<template>
  <van-tabbar v-model="active" route>
    <van-tabbar-item
      v-for="route in navRoutes"
      :key="route.path"
      :to="route.path"
      :icon="route.meta?.icon"
    >
      {{ route.meta?.title }}
    </van-tabbar-item>
  </van-tabbar>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { routes } from '@/router'

const active = ref(0)
const route = useRoute()
const navRoutes = routes.filter(r => r.meta?.title)

watch(() => route.path, (path) => {
  const idx = navRoutes.findIndex(r => r.path === path)
  if (idx >= 0) active.value = idx
}, { immediate: true })
</script>

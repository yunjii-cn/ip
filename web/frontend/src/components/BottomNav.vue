<template>
  <van-tabbar v-model="active">
    <van-tabbar-item
      v-for="route in navRoutes"
      :key="route.path"
      :icon="route.meta?.icon"
      @click="onTabClick(route)"
    >
      {{ route.meta?.title }}
    </van-tabbar-item>
  </van-tabbar>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { routes } from '@/router'

const active = ref(0)
const route = useRoute()
const router = useRouter()
const navRoutes = routes.filter(r => r.meta?.title)

function onTabClick(target: any) {
  // 显式控制路由跳转，避免依赖 van-tabbar 的 route 隐式行为
  if (target.path !== route.path) {
    router.push(target.path)
  }
}

watch(() => route.path, (path) => {
  const idx = navRoutes.findIndex(r => r.path === path)
  if (idx >= 0) active.value = idx
}, { immediate: true })
</script>

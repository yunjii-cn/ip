<template>
  <div class="app-container">
    <TopBar />
    <div class="main-content">
      <router-view />
    </div>
    <BottomNav />
  </div>
</template>

<script setup lang="ts">
import TopBar from '@/components/TopBar.vue'
import BottomNav from '@/components/BottomNav.vue'
</script>

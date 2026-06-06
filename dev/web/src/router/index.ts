import { createRouter, createWebHashHistory } from 'vue-router'

const routes = [
  { path: '/', redirect: '/line' },
  { path: '/line', name: 'line', component: () => import('@/views/LineView.vue'), meta: { title: '线路服务', icon: 'wap-nav' } },
  { path: '/proxy', name: 'proxy', component: () => import('@/views/ProxyView.vue'), meta: { title: '代理设置', icon: 'setting' } },
  { path: '/log', name: 'log', component: () => import('@/views/LogView.vue'), meta: { title: '运行日志', icon: 'records' } },
  { path: '/version', name: 'version', component: () => import('@/views/VersionView.vue'), meta: { title: '软件更新', icon: 'upgrade' } },
]

const router = createRouter({
  history: createWebHashHistory(),
  routes,
})

export default router
export { routes }

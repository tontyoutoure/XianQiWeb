// src/router/index.ts
import { createRouter, createWebHistory } from 'vue-router'
import NameInputPage from '@/views/NameInputPage.vue'

const routes = [
  {
    path: '/',
    name: 'NameInput',
    component: NameInputPage
  }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

export default router
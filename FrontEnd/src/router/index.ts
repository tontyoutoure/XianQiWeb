// src/router/index.ts
import { createRouter, createWebHistory } from 'vue-router'
import NameInputPage from '@/views/NameInputPage.vue'
import LobbyListPage from '@/views/LobbyListPage.vue'
import store from '@/store'

const routes = [
  {
    path: '/',
    name: 'NameInput',
    component: NameInputPage
  },
  {
    path: '/lobby-list',
    name: 'LobbyList',
    component: LobbyListPage,
    beforeEnter: (to, from, next) => {
      const playerName = store.state.user.playerName
      if (!playerName) {
        next({ name: 'NameInput' })
      } else {
        next()
      }
    }
  },
  {
    path: '/lobby/:id',
    name: 'Lobby',
    component: () => import('@/views/LobbyPage.vue'),
    beforeEnter: (to, from, next) => {
      const playerName = store.state.user.playerName
      if (!playerName) {
        next({ name: 'NameInput' })
      } else {
        next()
      }
    }
  }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

export default router
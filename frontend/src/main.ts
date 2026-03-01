import { createApp, defineComponent, h } from 'vue'
import { RouterView } from 'vue-router'

import { createAppRouter } from '@/app/router'
import { createAuthStoreForTest } from '@/stores/auth'
import './style.css'

const authStore = createAuthStoreForTest()
authStore.hydrateFromStorage()

const router = createAppRouter({ authStore, history: 'web' })

const AppRoot = defineComponent({
  name: 'AppRoot',
  components: { RouterView },
  render: () => h(RouterView),
})

const app = createApp(AppRoot)
app.use(router)

void router.isReady().finally(() => {
  app.mount('#app')
})

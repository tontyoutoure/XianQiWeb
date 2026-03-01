import { createApp, defineComponent, h } from 'vue'
import { RouterView } from 'vue-router'

import { createAppRouter } from '@/app/router'
import { createAuthApi } from '@/services/auth-api'
import { createAuthStoreForTest } from '@/stores/auth'
import './style.css'

const authStore = createAuthStoreForTest(
  {},
  {
    api: createAuthApi(),
  },
)
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

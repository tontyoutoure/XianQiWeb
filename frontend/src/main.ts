import { createApp, h } from 'vue'

import './style.css'

const App = {
  render: () =>
    h('main', { class: 'min-h-screen bg-slate-100 p-6 text-slate-900' }, [
      h('h1', { class: 'text-2xl font-bold' }, 'XianQiWeb Frontend Scaffold'),
      h(
        'p',
        { class: 'mt-2 text-sm text-slate-600' },
        'M7 配置文件已就绪，可在 src/pages 中继续实现业务页面。',
      ),
    ]),
}

createApp(App).mount('#app')

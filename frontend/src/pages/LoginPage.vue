<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'

import { useAuthStore } from '@/stores/auth'

const router = useRouter()
const authStore = useAuthStore()

const loginUsername = ref('')
const loginPassword = ref('')
const registerUsername = ref('')
const registerPassword = ref('')
const errorMessage = ref('')

async function onLoginSubmit() {
  errorMessage.value = ''
  try {
    await authStore.login({
      username: loginUsername.value,
      password: loginPassword.value,
    })
    await router.push('/lobby')
  } catch (error) {
    errorMessage.value = resolveErrorMessage(error)
  }
}

async function onRegisterSubmit() {
  errorMessage.value = ''
  try {
    await authStore.register({
      username: registerUsername.value,
      password: registerPassword.value,
    })
    await router.push('/lobby')
  } catch (error) {
    errorMessage.value = resolveErrorMessage(error)
  }
}

function resolveErrorMessage(error: unknown): string {
  if (error instanceof Error && error.message) {
    return error.message
  }
  return '请求失败，请稍后重试'
}
</script>

<template>
  <main class="mx-auto max-w-xl space-y-6 p-6">
    <h1 class="text-2xl font-bold">登录</h1>

    <section class="space-y-3 rounded border p-4">
      <h2 class="text-lg font-semibold">账号登录</h2>
      <label class="block">
        <span class="mb-1 block text-sm">用户名</span>
        <input
          data-testid="login-username"
          v-model="loginUsername"
          type="text"
          class="w-full rounded border px-3 py-2"
        />
      </label>
      <label class="block">
        <span class="mb-1 block text-sm">密码</span>
        <input
          data-testid="login-password"
          v-model="loginPassword"
          type="password"
          class="w-full rounded border px-3 py-2"
        />
      </label>
      <button
        data-testid="login-submit"
        type="button"
        class="rounded bg-slate-900 px-4 py-2 text-white"
        @click="onLoginSubmit"
      >
        登录
      </button>
    </section>

    <section class="space-y-3 rounded border p-4">
      <h2 class="text-lg font-semibold">注册并登录</h2>
      <label class="block">
        <span class="mb-1 block text-sm">用户名</span>
        <input
          data-testid="register-username"
          v-model="registerUsername"
          type="text"
          class="w-full rounded border px-3 py-2"
        />
      </label>
      <label class="block">
        <span class="mb-1 block text-sm">密码</span>
        <input
          data-testid="register-password"
          v-model="registerPassword"
          type="password"
          class="w-full rounded border px-3 py-2"
        />
      </label>
      <button
        data-testid="register-submit"
        type="button"
        class="rounded bg-slate-700 px-4 py-2 text-white"
        @click="onRegisterSubmit"
      >
        注册并登录
      </button>
    </section>

    <p v-if="errorMessage" class="text-sm text-red-600">{{ errorMessage }}</p>
  </main>
</template>

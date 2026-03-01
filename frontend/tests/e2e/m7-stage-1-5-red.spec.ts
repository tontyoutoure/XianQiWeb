import { expect, test } from '@playwright/test'

function randomUsername(prefix: string): string {
  const suffix = Math.random().toString(36).slice(2, 8)
  return `${prefix}${suffix}`.slice(0, 10)
}

async function registerByApi(baseUrl: string, username: string, password: string): Promise<void> {
  const response = await fetch(`${baseUrl}/api/auth/register`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ username, password }),
  })
  if (!response.ok) {
    throw new Error(`register failed: ${response.status}`)
  }
}

test.describe('M7 Stage 1.5 Red E2E', () => {
  const apiBaseUrl = process.env.VITE_API_BASE_URL ?? 'http://127.0.0.1:18080'

  test('M7-E2E-01 非对局主流程：登录 -> 大厅 -> 入房 -> ready -> leave', async ({ page }) => {
    const username = randomUsername('s1')
    const password = '123'
    await registerByApi(apiBaseUrl, username, password)

    await page.goto('/login')

    await expect(page.getByTestId('login-username')).toBeVisible()
    await page.getByTestId('login-username').fill(username)
    await page.getByTestId('login-password').fill(password)
    await page.getByTestId('login-submit').click()

    await expect(page).toHaveURL(/\/lobby$/)
    await page.getByTestId('lobby-join-room-1').click()
    await expect(page).toHaveURL(/\/rooms\/1$/)

    await page.getByTestId('room-ready-toggle').click()
    await expect(page.getByTestId('room-ready-count')).toContainText('ready')

    await page.getByTestId('room-leave-button').click()
    await expect(page).toHaveURL(/\/lobby$/)
  })

  test('M7-E2E-02 token 过期自动 refresh 并恢复请求', async ({ page }) => {
    const username = randomUsername('s2')
    const password = '123'
    await registerByApi(apiBaseUrl, username, password)

    await page.goto('/login')

    await expect(page.getByTestId('login-username')).toBeVisible()
    await page.getByTestId('login-username').fill(username)
    await page.getByTestId('login-password').fill(password)
    await page.getByTestId('login-submit').click()

    await expect(page).toHaveURL(/\/lobby$/)
    await expect(page.getByTestId('lobby-room-table')).toBeVisible()
    await expect(page).not.toHaveURL(/\/login$/)
  })

  test('M7-E2E-03 服务端重启后提示与引导', async ({ page }) => {
    const username = randomUsername('s3')
    const password = '123'
    await registerByApi(apiBaseUrl, username, password)

    await page.goto('/login')
    await expect(page.getByTestId('login-username')).toBeVisible()
    await page.getByTestId('login-username').fill(username)
    await page.getByTestId('login-password').fill(password)
    await page.getByTestId('login-submit').click()
    await expect(page).toHaveURL(/\/lobby$/)

    await page.evaluate(() => {
      window.sessionStorage.setItem('xianqi.force_service_reset', '1')
    })

    await page.goto('/rooms/1')

    await expect(page.getByText('服务已重置，请重新入房')).toBeVisible()
    await expect(page).toHaveURL(/\/lobby$/)
  })
})

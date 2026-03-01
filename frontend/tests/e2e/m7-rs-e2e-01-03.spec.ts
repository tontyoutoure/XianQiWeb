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

test.describe('M7 RS E2E 01-03', () => {
  const apiBaseUrl = process.env.VITE_API_BASE_URL ?? 'http://127.0.0.1:18080'

  test('M7-RS-E2E-01 登录闭环（真实 REST）', async ({ page }) => {
    const username = randomUsername('r1')
    const password = '123'
    await registerByApi(apiBaseUrl, username, password)

    await page.goto('/login')
    await page.getByTestId('login-username').fill(username)
    await page.getByTestId('login-password').fill(password)
    await page.getByTestId('login-submit').click()

    await expect(page).toHaveURL(/\/lobby$/)
    await expect(page.getByTestId('lobby-room-table')).toBeVisible()
    const joinButtons = page.locator('[data-testid^="lobby-join-room-"]')
    await expect(joinButtons.first()).toBeVisible()
    expect(await joinButtons.count()).toBeGreaterThan(0)
  })

  test('M7-RS-E2E-02 注册并登录闭环（真实 REST）', async ({ page }) => {
    const username = randomUsername('r2')
    const password = '123'

    await page.goto('/login')
    await page.getByTestId('register-username').fill(username)
    await page.getByTestId('register-password').fill(password)
    await page.getByTestId('register-submit').click()

    await expect(page).toHaveURL(/\/lobby$/)
    const joinButtons = page.locator('[data-testid^="lobby-join-room-"]')
    await expect(joinButtons.first()).toBeVisible()
    expect(await joinButtons.count()).toBeGreaterThan(0)

    await page.reload()
    await expect(page).toHaveURL(/\/lobby$/)
    await expect(page.getByTestId('lobby-room-table')).toBeVisible()
  })

  test('M7-RS-E2E-03 登录失败提示', async ({ page }) => {
    const username = randomUsername('r3')
    const password = '123'
    await registerByApi(apiBaseUrl, username, password)

    await page.goto('/login')
    await page.getByTestId('login-username').fill(username)
    await page.getByTestId('login-password').fill('wrong')
    await page.getByTestId('login-submit').click()

    await expect(page).toHaveURL(/\/login$/)
    await expect(page.getByText('invalid username or password')).toBeVisible()
  })
})

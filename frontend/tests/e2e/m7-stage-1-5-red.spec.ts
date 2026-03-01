import { expect, test } from '@playwright/test'

test.describe('M7 Stage 1.5 Red E2E', () => {
  test('M7-E2E-01 非对局主流程：登录 -> 大厅 -> 入房 -> ready -> leave', async ({ page }) => {
    await page.goto('/login')

    await expect(page.getByTestId('login-username')).toBeVisible()
    await page.getByTestId('login-username').fill('alice')
    await page.getByTestId('login-password').fill('secret')
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
    await page.goto('/login')

    await expect(page.getByTestId('login-username')).toBeVisible()
    await page.getByTestId('login-username').fill('alice')
    await page.getByTestId('login-password').fill('secret')
    await page.getByTestId('login-submit').click()

    await expect(page).toHaveURL(/\/lobby$/)
    await expect(page.getByTestId('lobby-room-table')).toBeVisible()
    await expect(page).not.toHaveURL(/\/login$/)
  })

  test('M7-E2E-03 服务端重启后提示与引导', async ({ page }) => {
    await page.goto('/login')
    await expect(page.getByTestId('login-username')).toBeVisible()
    await page.getByTestId('login-username').fill('alice')
    await page.getByTestId('login-password').fill('secret')
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

import { expect, test } from '@playwright/test'

test('M7-GATE-02 前端本地 E2E 可启动并访问 /login', async ({ page }) => {
  await page.goto('/login')

  await expect(page).toHaveURL(/\/login$/)
  await expect(page.getByRole('heading', { name: '登录', exact: true })).toBeVisible()
})

import { expect, test } from '@playwright/test'

test('home page routes to login', async ({ page }) => {
  await page.goto('/')
  await expect(page.getByRole('heading', { name: '登录', exact: true })).toBeVisible()
})

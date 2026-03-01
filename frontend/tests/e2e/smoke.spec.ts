import { expect, test } from '@playwright/test'

test('home page shows scaffold heading', async ({ page }) => {
  await page.goto('/')
  await expect(page.getByRole('heading', { name: 'XianQiWeb Frontend Scaffold' })).toBeVisible()
})

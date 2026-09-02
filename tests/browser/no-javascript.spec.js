// The README promises that with JavaScript off both views still show
// everything and simply stop filtering. That is the whole reason the filtering
// runs over markup that is already complete, so it is worth holding to.

const { test, expect } = require('@playwright/test');

test.use({ javaScriptEnabled: false });

test('the hierarchy shows the entire backlog, closed items included', async ({ page }) => {
  await page.goto('/plan');
  await expect(page.locator('[data-story]')).toHaveCount(6);
  await expect(page.locator('[data-story]:not([hidden])')).toHaveCount(6);
  await expect(page.locator('[data-epic]')).toHaveCount(2);
  // Nothing is hidden, because nothing ran to hide it.
  await expect(page.locator('#backlog-none')).toBeHidden();
});

test('the person view shows every open story', async ({ page }) => {
  await page.goto('/who');
  await expect(page.locator('[data-story]:not([hidden])')).toHaveCount(4);
  await expect(page.locator('#backlog-person-empty')).toBeHidden();
});

test('the controls are still rendered, just inert', async ({ page }) => {
  await page.goto('/plan');
  await expect(page.locator('#backlog-filters')).toBeVisible();
  await expect(page.locator('select[name=status] option')).toHaveCount(5);
  await expect(page.locator('select[name=label] option')).toHaveCount(4);
});

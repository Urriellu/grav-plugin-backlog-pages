// Priority by person: choosing somebody filters the list to what they could
// pick up. Capability, not assignment.
//
// The roster is Alex (software, hardware), Sam (research) and Nobody (nothing).
// Four stories are open: S-201 research, S-103 hardware+software, S-100 and
// S-101 software. S-100 waits on S-201, so it is blocked.

const { test, expect } = require('@playwright/test');

const OPEN = 4;

const shownRows = (page) => page.locator('[data-story]:not([hidden])');

async function visibleKeys(page) {
  return shownRows(page).locator('.backlog-key').allTextContents();
}

test.beforeEach(async ({ page }) => {
  await page.goto('/who');
});

test('opens on the first person with their work already filtered', async ({ page }) => {
  await expect(page.locator('#backlog-person')).toHaveValue('alex');
  // Global rank order: S-103 is 30, S-100 and S-101 both 40, tied and broken by key.
  expect(await visibleKeys(page)).toEqual(['S-103', 'S-100', 'S-101']);
  await expect(page.locator('#backlog-person-counts')).toHaveText(`3 of ${OPEN} open stories · 1 blocked`);
  await expect(page.locator('#backlog-person-note'))
    .toHaveText('Alex can pick up: software, hardware');
});

test('choosing somebody else re-filters the list', async ({ page }) => {
  await page.selectOption('#backlog-person', 'sam');
  expect(await visibleKeys(page)).toEqual(['S-201']);
  await expect(page.locator('#backlog-person-counts')).toHaveText(`1 of ${OPEN} open stories`);
  await expect(page.locator('#backlog-person-note')).toHaveText('Sam can pick up: research');
});

test('somebody who can pick up nothing is told so, not shown an empty page', async ({ page }) => {
  await page.selectOption('#backlog-person', 'nobody');
  await expect(shownRows(page)).toHaveCount(0);
  await expect(page.locator('#backlog-person-empty')).toBeVisible();
  await expect(page.locator('#backlog-person-note')).toHaveText('Nobody can pick up: nothing');
});

test('closed stories are never on offer, whoever is chosen', async ({ page }) => {
  for (const person of ['alex', 'sam', 'nobody']) {
    await page.selectOption('#backlog-person', person);
    const keys = await page.locator('[data-story]').locator('.backlog-key').allTextContents();
    expect(keys).not.toContain('S-102'); // done
    expect(keys).not.toContain('S-202'); // cancelled
  }
});

test('a person view can be linked to', async ({ page }) => {
  await page.selectOption('#backlog-person', 'sam');
  await expect(page).toHaveURL(/#person=sam$/);

  await page.goto(page.url());
  await expect(page.locator('#backlog-person')).toHaveValue('sam');
  expect(await visibleKeys(page)).toEqual(['S-201']);
});

test('an unknown person in the link falls back rather than blanking the page', async ({ page }) => {
  await page.goto('/who#person=someone-who-left');
  await expect(page.locator('#backlog-person')).toHaveValue('alex');
  expect(await visibleKeys(page)).toEqual(['S-103', 'S-100', 'S-101']);
});

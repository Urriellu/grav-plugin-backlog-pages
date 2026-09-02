// The hierarchy view's filtering, as a browser actually runs it.
//
// The PHP-level checks in tests/e2e assert that the markup carries the right
// data- attributes; nothing there runs the script that reads them. Everything
// below is behaviour no amount of reading the HTML can confirm.
//
// The fixture backlog is six stories: four open, one done (S-102) and one
// cancelled (S-202). See tests/e2e/fixtures/pages.

const { test, expect } = require('@playwright/test');

const OPEN = 4;
const ALL = 6;

const shownStories = (page) => page.locator('[data-story]:not([hidden])');
const shownEpics = (page) => page.locator('[data-epic]:not([hidden])');

/** The backlog keys currently on screen, in document order. */
async function visibleKeys(page) {
  return shownStories(page).locator('.backlog-key').allTextContents();
}

test.beforeEach(async ({ page }) => {
  await page.goto('/plan');
});

test('closed stories are hidden until asked for', async ({ page }) => {
  await expect(shownStories(page)).toHaveCount(OPEN);
  await expect(page.locator('#backlog-counts')).toHaveText(`${OPEN} of ${ALL} stories`);
  expect(await visibleKeys(page)).not.toContain('S-102');
  expect(await visibleKeys(page)).not.toContain('S-202');

  await page.check('input[name=closed]');
  await expect(shownStories(page)).toHaveCount(ALL);
  // Once nothing is filtered the count stops saying "of", because a count that
  // always reads "6 of 6" trains people to ignore it.
  await expect(page.locator('#backlog-counts')).toHaveText(`${ALL} stories`);
});

test('each epic reports how many of its stories are showing', async ({ page }) => {
  // E-02 holds S-201 (open) and S-202 (cancelled); E-01 holds three open and
  // one done.
  await expect(page.locator('[data-epic]').nth(0).locator('.backlog-count b')).toHaveText('1');
  await expect(page.locator('[data-epic]').nth(1).locator('.backlog-count b')).toHaveText('3');

  await page.check('input[name=closed]');
  await expect(page.locator('[data-epic]').nth(0).locator('.backlog-count b')).toHaveText('2');
  await expect(page.locator('[data-epic]').nth(1).locator('.backlog-count b')).toHaveText('4');
});

test('search matches a key', async ({ page }) => {
  await page.fill('input[name=q]', 'S-103');
  await expect(shownStories(page)).toHaveCount(1);
  expect(await visibleKeys(page)).toEqual(['S-103']);
});

test('search matches the summary, not only the title', async ({ page }) => {
  // S-103 alone carries `metadata.description`, which the plugin folds into the
  // row's data-text so that searching finds text the row never displays.
  await page.fill('input[name=q]', 'searchable summary');
  await expect(shownStories(page)).toHaveCount(1);
  expect(await visibleKeys(page)).toEqual(['S-103']);
});

test('search is case-insensitive', async ({ page }) => {
  await page.fill('input[name=q]', 's-103');
  await expect(shownStories(page)).toHaveCount(1);
});

test('filtering by label', async ({ page }) => {
  await page.selectOption('select[name=label]', 'research');
  // S-201 is open and labelled research; S-102 is too but is done.
  expect(await visibleKeys(page)).toEqual(['S-201']);

  await page.check('input[name=closed]');
  expect(await visibleKeys(page)).toEqual(['S-201', 'S-102']);
});

test('filtering by an open status', async ({ page }) => {
  await page.selectOption('select[name=status]', 'in-progress');
  expect(await visibleKeys(page)).toEqual(['S-103']);
});

test('filtering by a closed status shows the closed items', async ({ page }) => {
  // Asking for Done is an explicit request to see done work. If the "show done
  // and cancelled" toggle still applied here, choosing Done would return
  // nothing at all, which reads as a broken filter rather than a strict one.
  await page.selectOption('select[name=status]', 'done');
  expect(await visibleKeys(page)).toEqual(['S-102']);

  await page.selectOption('select[name=status]', 'cancelled');
  expect(await visibleKeys(page)).toEqual(['S-202']);
});

test('an epic with nothing left to show gets out of the way', async ({ page }) => {
  await page.selectOption('select[name=label]', 'hardware');
  // Only S-103, in E-01. E-02 has nothing to contribute.
  await expect(shownEpics(page)).toHaveCount(1);
  await expect(shownEpics(page).locator('summary .backlog-key')).toHaveText('E-01');
});

test('a filter that matches nothing says so', async ({ page }) => {
  await page.fill('input[name=q]', 'nothing-matches-this');
  await expect(shownStories(page)).toHaveCount(0);
  await expect(page.locator('#backlog-none')).toBeVisible();
  await expect(page.locator('#backlog-counts')).toHaveText(`0 of ${ALL} stories`);

  await page.click('#backlog-none-reset');
  await expect(shownStories(page)).toHaveCount(OPEN);
  await expect(page.locator('#backlog-none')).toBeHidden();
});

test('expand all and collapse all', async ({ page }) => {
  const epics = page.locator('[data-epic]');
  await page.click('button[data-all=close]');
  expect(await epics.evaluateAll((els) => els.map((e) => e.open))).toEqual([false, false]);

  await page.click('button[data-all=open]');
  expect(await epics.evaluateAll((els) => els.map((e) => e.open))).toEqual([true, true]);
});

test('clear puts every control back', async ({ page }) => {
  await page.fill('input[name=q]', 'S-103');
  await page.selectOption('select[name=status]', 'in-progress');
  await page.selectOption('select[name=label]', 'software');
  await page.check('input[name=closed]');

  await page.click('#backlog-reset');

  await expect(page.locator('input[name=q]')).toHaveValue('');
  await expect(page.locator('select[name=status]')).toHaveValue('');
  await expect(page.locator('select[name=label]')).toHaveValue('');
  await expect(page.locator('input[name=closed]')).not.toBeChecked();
  await expect(shownStories(page)).toHaveCount(OPEN);
});

test('a filtered view can be sent to somebody', async ({ page }) => {
  // State lives in the fragment for exactly this reason, so it has to survive
  // the round trip through the URL bar.
  await page.fill('input[name=q]', 'S-103');
  await page.selectOption('select[name=label]', 'software');
  await page.check('input[name=closed]');
  await expect(page).toHaveURL(/#.*q=S-103/);

  const url = page.url();
  await page.goto(url);

  await expect(page.locator('input[name=q]')).toHaveValue('S-103');
  await expect(page.locator('select[name=label]')).toHaveValue('software');
  await expect(page.locator('input[name=closed]')).toBeChecked();
  expect(await visibleKeys(page)).toEqual(['S-103']);
});

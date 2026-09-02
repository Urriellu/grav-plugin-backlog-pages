// Blocked stories, as a browser runs them.
//
// The e2e checks assert that the markup says which stories are blocked; nothing
// there runs the script that acts on it. What follows is the acting on it.
//
// In the fixture backlog S-100 waits on S-201, which is open, so exactly one of
// the four open stories cannot be picked up. S-103 waits on S-102, which is
// done, so it is not blocked -- the derivation, not a flag, is what these drive.

const { test, expect } = require('@playwright/test');

const OPEN = 4;
const ALL = 6;

const shownStories = (page) => page.locator('[data-story]:not([hidden])');
const blockedRows = (page) => page.locator('[data-story][data-blocked="1"]');

async function visibleKeys(page) {
  return shownStories(page).locator('.backlog-key').allTextContents();
}

test.describe('the hierarchy', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/plan');
  });

  test('marks the blocked story and names what it waits on', async ({ page }) => {
    const marker = blockedRows(page).locator('.backlog-blocked');
    await expect(marker).toHaveCount(1);
    // The emoji says stop but not until what, so the blocker has to be readable
    // both on hover and to a screen reader.
    await expect(marker).toHaveAttribute('title', 'Blocked by S-201');
    await expect(marker).toHaveAttribute('aria-label', 'Blocked by S-201');
  });

  test('marks only what is waiting on something still open', async ({ page }) => {
    // S-103 depends on S-102, which is done. A story whose blocker has closed is
    // ready, and nobody had to go back and unmark it.
    expect(await blockedRows(page).locator('.backlog-key').allTextContents()).toEqual(['S-100']);
  });

  test('ready only drops what cannot be started', async ({ page }) => {
    expect(await visibleKeys(page)).toContain('S-100');

    await page.check('input[name=unblocked]');
    await expect(shownStories(page)).toHaveCount(OPEN - 1);
    expect(await visibleKeys(page)).not.toContain('S-100');
  });

  test('says how many of the stories on screen are blocked', async ({ page }) => {
    await expect(page.locator('#backlog-counts')).toHaveText(`${OPEN} of ${ALL} stories · 1 blocked`);

    // With the blocked ones filtered out there are none left on screen, so the
    // tail has nothing left to report.
    await page.check('input[name=unblocked]');
    await expect(page.locator('#backlog-counts')).toHaveText(`${OPEN - 1} of ${ALL} stories`);
  });

  test('ready only survives the round trip through the URL', async ({ page }) => {
    await page.check('input[name=unblocked]');
    await expect(page).toHaveURL(/#.*unblocked=1/);

    await page.goto(page.url());
    await expect(page.locator('input[name=unblocked]')).toBeChecked();
    expect(await visibleKeys(page)).not.toContain('S-100');
  });

  test('clear puts ready only back with everything else', async ({ page }) => {
    await page.check('input[name=unblocked]');
    await page.click('#backlog-reset');

    await expect(page.locator('input[name=unblocked]')).not.toBeChecked();
    await expect(shownStories(page)).toHaveCount(OPEN);
  });
});

test.describe('priority by person', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/who');
  });

  test('marks a blocked story in the list somebody picks from', async ({ page }) => {
    // Alex picks up software, which is what S-100 carries -- so it is on offer,
    // and being on offer is exactly why it has to say it cannot be started.
    await expect(blockedRows(page).locator('.backlog-blocked')).toHaveCount(1);
    await expect(page.locator('#backlog-person-counts'))
      .toHaveText(`3 of ${OPEN} open stories · 1 blocked`);
  });

  test('ready only leaves what this person could actually start', async ({ page }) => {
    await page.check('#backlog-person-unblocked');
    expect(await visibleKeys(page)).toEqual(['S-103', 'S-101']);
    // Still counted while hidden: the point of the number is that the story
    // exists and is waiting on something.
    await expect(page.locator('#backlog-person-counts'))
      .toHaveText(`2 of ${OPEN} open stories · 1 blocked`);
  });

  test('counts the blocked work of the person chosen, not everybody', async ({ page }) => {
    // Sam picks up research, which is S-201, and nothing is holding that up.
    await page.selectOption('#backlog-person', 'sam');
    await expect(page.locator('#backlog-person-counts')).toHaveText(`1 of ${OPEN} open stories`);
  });

  test('a link carries ready only along with the person', async ({ page }) => {
    await page.check('#backlog-person-unblocked');
    await expect(page).toHaveURL(/#person=alex&unblocked=1$/);

    await page.goto(page.url());
    await expect(page.locator('#backlog-person-unblocked')).toBeChecked();
    expect(await visibleKeys(page)).toEqual(['S-103', 'S-101']);
  });
});

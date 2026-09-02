const path = require('path');

// The browser tests drive the same fixture site the PHP-level checks assert on,
// served by the same script, so there is one definition of "the test backlog"
// rather than two that drift.
const gravRoot = process.env.GRAV_ROOT;
if (!gravRoot) {
  throw new Error(
    'Set GRAV_ROOT to a Grav install.\n' +
    '  tests/e2e/install-grav.sh 2.0 /tmp/grav20\n' +
    '  GRAV_ROOT=/tmp/grav20 npx playwright test --config tests/browser/playwright.config.js'
  );
}

const port = Number(process.env.PORT || 8765);

module.exports = {
  testDir: __dirname,
  timeout: 30_000,
  expect: { timeout: 5_000 },
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
  reporter: [['list']],

  // `php -S` serves one request at a time, so parallel workers would spend
  // their time queueing behind each other rather than finding anything.
  workers: 1,

  use: {
    baseURL: `http://127.0.0.1:${port}`,
    trace: 'retain-on-failure',
  },

  webServer: {
    command:
      `python3 ${path.join(__dirname, '..', 'e2e', 'run.py')}` +
      ` --grav ${gravRoot} --serve --port ${port}`,
    url: `http://127.0.0.1:${port}/plan`,
    reuseExistingServer: !process.env.CI,
    // Grav compiles its Twig and page cache on the first request.
    timeout: 180_000,
    stdout: 'pipe',
    stderr: 'pipe',
  },
};

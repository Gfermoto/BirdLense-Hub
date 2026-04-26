import { test, expect } from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';

/**
 * Regression guard for [#117](https://github.com/Gfermoto/BirdLense-Hub/issues/117).
 * Run with stack up (`make start` in app/) and `make test-e2e` or `npm test` in app/e2e.
 */
test.describe('Accessibility (axe)', () => {
  test.describe.configure({ timeout: 45000 });

  const paths = [
    '/',
    '/timeline',
    '/timeline?review=1',
    '/timeline?favorites=1',
    '/migration-calendar',
    '/videos/0',
  ];

  for (const path of paths) {
    test(`no critical or serious violations: ${path}`, async ({ page }) => {
      await page.goto(path, { waitUntil: 'networkidle' });
      const results = await new AxeBuilder({ page })
        .withTags(['wcag2a', 'wcag2aa'])
        .analyze();
      const bad = results.violations.filter(
        (v) => v.impact === 'critical' || v.impact === 'serious',
      );
      expect.soft(bad, JSON.stringify(bad, null, 2)).toEqual([]);
    });
  }
});

import playwrightPkg from '../app/e2e/node_modules/@playwright/test/index.js';
import axePkg from '../app/e2e/node_modules/@axe-core/playwright/dist/index.js';
const { chromium } = playwrightPkg;
const AxeBuilder = axePkg.default || axePkg;
import fs from 'node:fs/promises';

const base = 'http://127.0.0.1:5177';
const pages = ['/', '/timeline', '/favorites', '/library', '/system', '/settings', '/species-directory', '/live'];
const viewports = [
  { name: 'mobile-375', width: 375, height: 812 },
  { name: 'tablet-768', width: 768, height: 1024 },
  { name: 'desktop-1280', width: 1280, height: 900 },
];
const rows = [];
const browser = await chromium.launch({ headless: true });
await fs.mkdir('.review-automation/screenshots', { recursive: true });
await fs.mkdir('.review-automation/logs', { recursive: true });
for (const route of pages) {
  for (const vp of viewports) {
    const context = await browser.newContext({ viewport: { width: vp.width, height: vp.height } });
    const page = await context.newPage();
    const consoleMessages = [];
    const pageErrors = [];
    const failedRequests = [];
    page.on('console', (msg) => {
      if (['error', 'warning'].includes(msg.type())) consoleMessages.push(`${msg.type()}: ${msg.text()}`);
    });
    page.on('pageerror', (err) => pageErrors.push(String(err.stack || err.message || err)));
    page.on('requestfailed', (req) => failedRequests.push(`${req.method()} ${req.url()} ${req.failure()?.errorText || ''}`));
    const url = base + route;
    let status = 'n/a';
    try {
      const res = await page.goto(url, { waitUntil: 'networkidle', timeout: 20000 });
      status = String(res?.status() ?? 'n/a');
      await page.screenshot({ path: `.review-automation/screenshots/${route.replaceAll('/', '_') || 'root'}-${vp.name}.png`, fullPage: true });
      const perf = await page.evaluate(() => {
        const nav = performance.getEntriesByType('navigation')[0];
        const paint = Object.fromEntries(performance.getEntriesByType('paint').map((p) => [p.name, Math.round(p.startTime)]));
        return {
          fcp: paint['first-contentful-paint'] ?? null,
          domContentLoaded: nav ? Math.round(nav.domContentLoadedEventEnd) : null,
          load: nav ? Math.round(nav.loadEventEnd) : null,
          cls: performance.getEntriesByType('layout-shift').reduce((s, e) => s + (!e.hadRecentInput ? e.value : 0), 0),
        };
      });
      const axe = await new AxeBuilder({ page }).analyze();
      rows.push({ route, viewport: vp.name, status, consoleMessages, pageErrors, failedRequests, perf, axeViolations: axe.violations.length, axe: axe.violations.map(v => ({ id: v.id, impact: v.impact, nodes: v.nodes.length, help: v.help })) });
    } catch (e) {
      rows.push({ route, viewport: vp.name, status, error: String(e), consoleMessages, pageErrors, failedRequests });
    }
    await context.close();
  }
}
// Error API simulation: abort API calls on overview; verify ErrorBoundary does not blank page.
{
  const context = await browser.newContext({ viewport: { width: 1280, height: 900 } });
  const page = await context.newPage();
  const consoleMessages = [];
  page.on('console', (msg) => { if (['error', 'warning'].includes(msg.type())) consoleMessages.push(`${msg.type()}: ${msg.text()}`); });
  await page.route('**/api/**', (route) => route.abort('failed'));
  let title = '';
  try {
    await page.goto(base + '/', { waitUntil: 'domcontentloaded', timeout: 15000 });
    await page.waitForTimeout(2500);
    title = (await page.locator('body').innerText({ timeout: 3000 })).slice(0, 500);
    await page.screenshot({ path: '.review-automation/screenshots/api-error-overview-desktop.png', fullPage: true });
  } catch (e) {
    title = `ERROR: ${String(e)}`;
  }
  rows.push({ route: '/', viewport: 'desktop-api-abort', apiAbortBodySample: title, consoleMessages });
  await context.close();
}
await browser.close();
await fs.writeFile('.review-automation/logs/ui-review-results.json', JSON.stringify(rows, null, 2));
let md = '# Wave 3: UI report\n\n';
md += '| Route | Viewport | HTTP | Console warn/error | Page errors | Failed req | FCP ms | Load ms | CLS | Axe violations |\n|---|---|---:|---:|---:|---:|---:|---:|---:|---:|\n';
for (const r of rows) {
  md += `| \`${r.route}\` | ${r.viewport} | ${r.status ?? ''} | ${r.consoleMessages?.length ?? 0} | ${r.pageErrors?.length ?? 0} | ${r.failedRequests?.length ?? 0} | ${r.perf?.fcp ?? ''} | ${r.perf?.load ?? ''} | ${r.perf?.cls ?? ''} | ${r.axeViolations ?? ''} |\n`;
}
md += '\n## Notes\n- Screenshots: `.review-automation/screenshots/`\n- Raw JSON: `.review-automation/logs/ui-review-results.json`\n- Lighthouse not run: Chrome lighthouse package is not part of repo; Playwright PerformanceNavigationTiming used as lightweight proxy.\n';
await fs.writeFile('.review-automation/wave3-ui-report.md', md);

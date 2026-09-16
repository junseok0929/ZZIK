import { expect, type BrowserContext, type Page } from '@playwright/test';

export async function login(page: Page, email = 'jisu@moacut.local') {
  await page.goto('/');
  await page.getByLabel('이메일', { exact: true }).fill(email);
  await page.getByLabel('비밀번호', { exact: true }).fill('MoacutDemo123!');
  await page.getByRole('button', { name: '로그인', exact: true }).click();
  await expect(page.locator('.app-shell')).toBeVisible();
  await expect(page.locator('.album-header h1, .album-home h1')).toBeVisible();
}

export async function api(context: BrowserContext, path: string, method = 'GET', data?: unknown) {
  const session = await context.request.get('/api/auth/me');
  expect(session.ok(), await session.text()).toBeTruthy();
  const { csrf_token } = await session.json();
  const result = await context.request.fetch('/api' + path, { method, data, headers: { 'X-CSRF-Token': csrf_token } });
  expect(result.ok(), `${method} ${path}: ${await result.text()}`).toBeTruthy();
  return result;
}

export async function noHorizontalOverflow(page: Page) {
  const sizes = await page.evaluate(() => ({
    viewport: document.documentElement.clientWidth,
    document: document.documentElement.scrollWidth,
    body: document.body.scrollWidth,
  }));
  expect(sizes.document).toBeLessThanOrEqual(sizes.viewport + 1);
  expect(sizes.body).toBeLessThanOrEqual(sizes.viewport + 1);
}

export async function selectVersion(page: Page, name: string) {
  await page.locator('.editor-version').filter({ has: page.getByText(name, { exact: true }) }).click();
  await page.getByRole('navigation', { name: '사진 상세 메뉴' }).getByRole('button', { name: '함께 고르기', exact: true }).click();
}

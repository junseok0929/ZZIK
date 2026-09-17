import { test, expect } from '@playwright/test';
import { readFile } from 'node:fs/promises';
import path from 'node:path';
import { api, login, noHorizontalOverflow, selectVersion } from './helpers';

const assets = path.resolve('public/demo');

test('two members upload, edit, approve, download and revoke an isolated album', async ({ page, context, browser }, testInfo) => {
  test.setTimeout(150_000);
  const errors: string[] = [];
  page.on('pageerror', error => errors.push(error.message));
  const second = await browser.newContext({ baseURL: testInfo.project.use.baseURL as string || 'http://127.0.0.1:5173', viewport: { width: 1440, height: 1000 } });
  const memberPage = await second.newPage();
  let albumId = '';
  try {
    await login(page);
    await login(memberPage, 'minji@moacut.local');
    await noHorizontalOverflow(page);
    const albumName = `브라우저 검증 ${Date.now()}`;
    await page.getByRole('button', { name: '새 앨범 만들기', exact: true }).click();
    const create = page.getByRole('dialog', { name: '새 앨범 만들기' });
    await create.getByLabel('앨범 이름').fill(albumName);
    await create.getByLabel('앨범 소개').fill('Playwright가 만든 독립 검증 앨범');
    const created = page.waitForResponse(response => response.url().endsWith('/api/albums') && response.request().method() === 'POST');
    await create.getByRole('button', { name: '앨범 만들기', exact: true }).click();
    const album = await (await created).json();
    expect(album.id).toBeTruthy();
    albumId = album.id;
    await expect(page.locator('.album-header h1')).toContainText(albumName);

    await memberPage.locator('.join-link').click();
    const join = memberPage.getByRole('dialog', { name: '초대코드로 참여하기' });
    await join.getByLabel('초대코드', { exact: true }).fill(album.invite_code);
    await join.getByRole('button', { name: '앨범 참여하기' }).click();
    await expect(memberPage.locator('.album-header h1')).toContainText(albumName);
    // Reference registration is setup; the primary upload/editor/consent journey runs through the UI.
    for (const [session, slug, name] of [[context, 'jisu', '지수'], [second, 'minji', '민지']] as const) {
      const auth = await (await session.request.get('/api/auth/me')).json();
      const response = await session.request.post(`/api/albums/${albumId}/people`, {
        headers: { 'X-CSRF-Token': auth.csrf_token },
        multipart: { name, user_id: auth.user.id, file: { name: `${slug}.jpg`, mimeType: 'image/jpeg', buffer: await readFile(path.join(assets, `avatar-${slug}.jpg`)) } },
      });
      expect(response.ok(), await response.text()).toBeTruthy();
    }
    await page.reload();
    await expect(page.locator('.people-strip')).toContainText('민지');
    await page.getByRole('button', { name: '사진 올리기', exact: true }).first().click();
    const upload = page.getByRole('dialog', { name: '사진 올리기' });
    const sample = await readFile(path.join(assets, 'photo-02.jpg'));
    await upload.getByLabel('업로드할 사진').setInputFiles([
      { name: 'E2E_shared.jpg', mimeType: 'image/jpeg', buffer: sample },
      { name: 'E2E_new_photo.jpg', mimeType: 'image/jpeg', buffer: Buffer.concat([sample, Buffer.from('new-original-not-a-fixture')]) },
      { name: 'E2E_unsupported.heic', mimeType: 'image/heic', buffer: Buffer.from('unsupported-file') },
    ]);
    await expect(upload).toContainText('JPEG 또는 PNG만 지원해요');
    await upload.getByRole('button', { name: '사진 올리기', exact: true }).click();
    await expect(upload).toContainText('총 3장 중 2장 저장 완료');
    await upload.getByRole('button', { name: 'E2E_unsupported.heic 제외' }).click();
    await upload.getByRole('button', { name: '닫기', exact: true }).click();
    let shared: { id: string; versions?: { id: string; name: string }[] };
    await expect.poll(async () => {
      const photos = await (await api(context, `/albums/${albumId}/photos`)).json();
      shared = photos.items.find((item: { filename: string }) => item.filename === 'E2E_shared.jpg');
      return photos.items.map((item: { analysis_status: string }) => item.analysis_status).sort();
    }, { timeout: 45_000 }).toEqual(['completed', 'failed']);
    const results = await (await api(context, `/albums/${albumId}/photos`)).json();
    const failed = results.items.find((item: { filename: string }) => item.filename === 'E2E_new_photo.jpg');
    expect(failed.analysis_error).toContain('실제 분석 연결 필요');
    expect(results.total).toBe(2);
    await page.reload();
    await page.getByLabel('사진 검색', { exact: true }).fill('E2E_shared');
    await expect(page.locator('.photo-card')).toHaveCount(1);
    await page.getByRole('button', { name: '검색어 지우기' }).click();
    await expect(page.locator('.photo-card')).toHaveCount(2);
    await page.locator('.filter-pills').getByRole('button', { name: '함께', exact: true }).click();
    await expect(page.locator('.photo-card')).toHaveCount(1);
    await noHorizontalOverflow(page);
    await page.screenshot({ path: testInfo.outputPath('desktop-library.png'), fullPage: true });
    await testInfo.attach('Desktop library', { path: testInfo.outputPath('desktop-library.png'), contentType: 'image/png' });
    await page.getByRole('button', { name: 'E2E_shared.jpg 사진 정보', exact: true }).click();
    await page.getByRole('button', { name: '사진 크게 보고 보정하기' }).click();
    const editor = page.getByRole('dialog', { name: '사진 보정 및 함께 고르기' });
    await expect(editor).toBeVisible();
    await editor.getByRole('slider', { name: '밝기' }).press('ArrowRight');
    await editor.getByRole('slider', { name: '밝기' }).press('ArrowRight');
    await editor.getByRole('slider', { name: '채도' }).press('ArrowLeft');
    await editor.getByLabel('새 보정본 이름').fill('우리의 밝은 순간');
    await editor.getByRole('button', { name: '새 보정본 저장', exact: true }).click();
    await expect(editor.getByRole('heading', { name: '우리의 밝은 순간', exact: true })).toBeVisible();
    await editor.getByRole('checkbox', { name: '사진의 등장 멤버와 승인 대상을 확인했어요.' }).check();
    await editor.getByRole('button', { name: '확인 요청 보내기' }).click();
    await expect(editor).toContainText('0 / 2명 승인');
    await editor.getByRole('button', { name: '이 보정본 승인', exact: true }).click();
    await expect(editor).toContainText('1 / 2명 승인');

    await memberPage.reload();
    await memberPage.getByRole('button', { name: 'E2E_shared.jpg 보정하기', exact: true }).click();
    await selectVersion(memberPage, '우리의 밝은 순간');
    // The mobile photo-side approval controls use the same persisted consensus flow.
    await memberPage.setViewportSize({ width: 390, height: 844 });
    await memberPage.getByRole('navigation', { name: '사진 상세 메뉴' }).getByRole('button', { name: '사진 보정', exact: true }).click();
    const quickApproval = memberPage.locator('.editor-mobile-review');
    await expect(quickApproval).toContainText('1 / 2명 승인');
    await quickApproval.getByRole('button', { name: '이 보정본 승인', exact: true }).click();
    await expect(quickApproval).toContainText('2 / 2명 승인');
    await noHorizontalOverflow(memberPage);
    await memberPage.getByRole('button', { name: '사진 상세 닫기' }).scrollIntoViewIfNeeded();
    await memberPage.screenshot({ path: testInfo.outputPath('mobile-approval.png') });
    await testInfo.attach('Mobile approval', { path: testInfo.outputPath('mobile-approval.png'), contentType: 'image/png' });
    await quickApproval.getByRole('button', { name: '승인 상세 보기' }).click();
    await memberPage.setViewportSize({ width: 1440, height: 1000 });
    await expect(memberPage.getByRole('dialog')).toContainText('2 / 2명 승인');
    await expect(editor.getByRole('button', { name: '최종본으로 정하기' })).toBeVisible({ timeout: 15_000 });
    await editor.getByRole('button', { name: '최종본으로 정하기' }).click();
    await expect(editor).toContainText('최종본으로 선택됨');
    await editor.getByRole('button', { name: '슬라이더로 비교' }).click();
    await expect(editor.getByRole('slider', { name: '원본과 보정본 비교 위치' })).toBeVisible();
    await noHorizontalOverflow(page);
    await page.screenshot({ path: testInfo.outputPath('desktop-approved-editor.png') });
    await testInfo.attach('Desktop approved editor', { path: testInfo.outputPath('desktop-approved-editor.png'), contentType: 'image/png' });
    await editor.locator('.editor-download summary').click();
    const downloadEvent = page.waitForEvent('download');
    await editor.getByRole('button', { name: /최종본 다운로드/ }).click();
    const download = await downloadEvent;
    expect(download.suggestedFilename()).toContain('-v1.jpg');
    await download.saveAs(testInfo.outputPath('approved-version.jpg'));
    // Final selection and version settings survive a page reload.
    await page.reload();
    await page.getByRole('button', { name: 'E2E_shared.jpg 보정하기', exact: true }).click();
    await expect(page.locator('.editor-version.active')).toContainText('우리의 밝은 순간');
    await expect(page.getByRole('slider', { name: '밝기' })).toHaveValue('1.02');
    await expect(page.getByRole('slider', { name: '채도' })).toHaveValue('0.99');
    await memberPage.getByRole('button', { name: '내 승인 취소', exact: true }).click();
    await expect.poll(async () => {
      const photo = await (await api(context, `/photos/${shared!.id}`)).json();
      return photo.final_version_id;
    }).toBeNull();
    await page.getByRole('navigation', { name: '사진 상세 메뉴' }).getByRole('button', { name: '함께 고르기', exact: true }).click();
    await expect(page.getByRole('dialog')).toContainText('1 / 2명 승인');
    expect(errors).toEqual([]);
  } finally {
    if (albumId) await api(context, `/albums/${albumId}`, 'DELETE');
    await second.close();
  }
});

import {test, expect} from '@playwright/test';

test('public guide supports keyboard language switching and policy navigation', async ({page}) => {
  const failures = [];
  page.on('pageerror', error => failures.push(error.message));
  await page.goto('/guide');
  await expect(page).toHaveTitle('Seller guide · Milaan');
  const guide = page.locator('#help-dialog');
  await expect(guide).toBeVisible();
  await expect(page.locator('#guide-en')).toBeVisible();
  await expect(page.locator('#guide-ur')).toBeHidden();
  const urdu = guide.getByRole('button', {name: 'Roman Urdu', exact: true});
  await urdu.focus();
  await page.keyboard.press('Enter');
  await expect(urdu).toHaveAttribute('aria-pressed', 'true');
  await expect(page.locator('#guide-ur')).toBeVisible();
  await expect(page.locator('#guide-en')).toBeHidden();
  const english = guide.getByRole('button', {name: 'English', exact: true});
  await english.focus();
  await page.keyboard.press('Space');
  await expect(english).toHaveAttribute('aria-pressed', 'true');
  await expect(page.locator('#guide-en')).toBeVisible();
  await page.keyboard.press('Escape');
  await expect(guide).toBeHidden();
  for (const route of ['/privacy', '/terms', '/about']) {
    await page.goto(route);
    await expect(page.locator('h1')).toBeVisible();
    await expect(page.locator('link[rel="canonical"]')).toHaveAttribute('href', 'http://127.0.0.1:8765' + route);
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  }
  expect(failures).toEqual([]);
});


test('payment preview is keyboard accessible and motion preference persists', async ({page}) => {
  await page.goto('/');
  const preview=page.getByRole('button',{name:/Illustrative payment.*explore fictional demo/});
  await preview.focus();
  await page.keyboard.press('Enter');
  await expect(page.locator('#workspace')).toBeVisible();
  await page.goto('/');
  const toggle=page.getByRole('button',{name:/Pause animation|Resume animation/});
  await toggle.click();
  const saved=await page.evaluate(()=>localStorage.getItem('milaan-motion'));
  expect(['off','on']).toContain(saved);
  await page.reload();
  expect(await page.evaluate(()=>localStorage.getItem('milaan-motion'))).toBe(saved);
  await expect(page.locator('#confirm-dialog[aria-labelledby="confirm-title"]')).toHaveCount(1);
});

import { expect, test } from '@playwright/test';

test.describe('PWA Service Worker', () => {
	test('service worker removes itself instead of controlling the page', async ({ page }) => {
		await page.goto('/');

		await page.waitForFunction(
			() => navigator.serviceWorker.getRegistration().then((registration) => !registration)
		);

		const controller = await page.evaluate(() => navigator.serviceWorker.controller);

		expect(controller).toBeNull();
	});

	test('service worker does not precache the Vite build', async ({ page }) => {
		const swResponse = await page.request.get('/sw.js');
		const swContent = await swResponse.text();

		expect(swResponse.ok()).toBeTruthy();
		expect(swContent).toMatch(/unregister/);
		expect(swContent).not.toMatch(/_app\/immutable\/bundle\./);
		expect(swContent).not.toMatch(/workbox-/);
		expect(swContent).not.toMatch(/NavigationRoute/);
		expect(swContent).not.toMatch(/api-cache/);
	});

	test('version.json is accessible and contains version', async ({ page }) => {
		const versionResponse = await page.request.get('/_app/version.json');

		expect(versionResponse.ok()).toBeTruthy();

		const versionData = await versionResponse.json();

		expect(versionData).toHaveProperty('version');
		expect(typeof versionData.version).toBe('string');
		expect(versionData.version.length).toBeGreaterThan(0);
	});

	test('manifest.webmanifest is accessible and valid', async ({ page }) => {
		const response = await page.request.get('/manifest.webmanifest');

		expect(response.ok()).toBeTruthy();

		const manifest = await response.json();

		expect(manifest).toHaveProperty('name', 'llama-ui');
		expect(manifest).toHaveProperty('short_name', 'llama-ui');
		expect(manifest).toHaveProperty('start_url', './');
		expect(manifest).toHaveProperty('display', 'standalone');
		expect(manifest.icons).toBeTruthy();
		expect(manifest.icons.length).toBeGreaterThan(0);
	});

	test('index.html contains content-hashed bundle references', async ({ page }) => {
		const response = await page.request.get('/');

		expect(response.ok()).toBeTruthy();

		const html = await response.text();

		// SvelteKit outputs content-hashed bundle names in _app/immutable/
		expect(html).toMatch(/href="(\.\/|\/)_app\/immutable\/bundle\.[a-zA-Z0-9_-]+\.js"/);
		expect(html).toMatch(/href="(\.\/|\/)_app\/immutable\/assets\/bundle\.[a-zA-Z0-9_-]+\.css"/);
		expect(html).toMatch(/import\("(\.\/|\/)_app\/immutable\/bundle\.[a-zA-Z0-9_-]+\.js"\)/);
	});
});

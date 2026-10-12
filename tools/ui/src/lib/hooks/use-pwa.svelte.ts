import { useRegisterSW } from 'virtual:pwa-register/svelte';

/**
 * Registers the self-destroying service worker once so a previously installed
 * worker can drop its caches. There is no periodic update check.
 */
export function usePwa() {
	const {
		needRefresh: pwaNeedRefresh,
		updateServiceWorker
	} = useRegisterSW({
		onRegisterError(error: unknown) {
			console.error('[PWA] SW registration error:', error);
		}
	});

	return {
		/** Writable that is true when a PWA service worker update is available */
		get needRefresh() {
			return pwaNeedRefresh;
		},
		/** Automatic version-mismatch reloads are disabled */
		get needRefreshByStorage() {
			return false;
		},
		updateServiceWorker
	};
}

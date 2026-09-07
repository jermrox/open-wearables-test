import { apiGet } from './api';
import { redis } from './redis';

export type Provider = {
	provider: string;
	name: string;
	has_cloud_api: boolean;
	is_enabled: boolean;
	/** Relative to the API base, which the browser cannot reach under cookie sessions. */
	icon_url: string;
};

const CACHE_KEY = 'ow:providers:enabled';
const TTL_SECONDS = 60;

/**
 * Enabled only: a filter chip for a provider nobody can connect is noise.
 *
 * Cached because the list is near-static but the call is not rare — every
 * search keystroke, sort, page and mutation re-runs the loader. Unlike the
 * session store this fails **open**: an unreachable Redis costs an API call,
 * not a login.
 */
export async function fetchProviders(accessToken: string): Promise<Provider[]> {
	try {
		const cached = await redis().get(CACHE_KEY);
		if (cached) return JSON.parse(cached) as Provider[];
	} catch {
		// Fall through to the API.
	}

	const providers = await apiGet<Provider[]>(
		'/api/v1/oauth/providers?enabled_only=true',
		accessToken
	);

	redis()
		.set(CACHE_KEY, JSON.stringify(providers), 'EX', TTL_SECONDS)
		.catch(() => {});

	return providers;
}

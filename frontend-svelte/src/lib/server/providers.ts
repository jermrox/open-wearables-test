import { apiGet } from './api';

export type Provider = {
	provider: string;
	name: string;
	has_cloud_api: boolean;
	is_enabled: boolean;
	/** Relative to the API base, which the browser cannot reach under cookie sessions. */
	icon_url: string;
};

/** Enabled only: a filter chip for a provider nobody can connect is noise. */
export async function fetchProviders(accessToken: string): Promise<Provider[]> {
	return apiGet<Provider[]>('/api/v1/oauth/providers?enabled_only=true', accessToken);
}

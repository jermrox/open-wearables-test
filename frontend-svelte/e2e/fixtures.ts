export const CREDENTIALS = { email: 'dev@example.com', password: 'correct-horse' };

export const DEVELOPER = {
	id: '00000000-0000-4000-8000-000000000001',
	email: CREDENTIALS.email,
	first_name: 'Test',
	last_name: 'Developer',
	created_at: '2026-01-01T00:00:00Z'
};

export const PROVIDERS = ['garmin', 'oura', 'whoop', 'suunto'];

export const PROVIDER_SETTINGS = PROVIDERS.map((provider) => ({
	provider,
	name: provider[0].toUpperCase() + provider.slice(1),
	has_cloud_api: true,
	is_enabled: true,
	icon_url: `/static/provider-icons/${provider}.svg`
}));

/** 47 users: enough for three pages at 20, with a memorable one to search for. */
export const USERS = Array.from({ length: 47 }, (_, index) => {
	const n = index + 1;
	return {
		id: `00000000-0000-4000-8000-${String(n).padStart(12, '0')}`,
		created_at: new Date(Date.UTC(2026, 0, 1 + n)).toISOString(),
		first_name: n === 7 ? 'Zofia' : `User${n}`,
		last_name: n === 7 ? 'Kowalska' : 'Test',
		email: n === 7 ? 'zofia@example.com' : `user${n}@example.com`,
		last_synced_at: n % 3 === 0 ? null : new Date(Date.UTC(2026, 8, 1 + (n % 4))).toISOString(),
		last_synced_provider: n % 3 === 0 ? null : PROVIDERS[n % PROVIDERS.length],
		has_active_connection: n % 3 !== 0,
		connections:
			n % 3 === 0
				? []
				: [
						{
							provider: PROVIDERS[n % PROVIDERS.length],
							status: 'active' as const,
							last_synced_at: new Date(Date.UTC(2026, 8, 1 + (n % 4))).toISOString()
						}
					]
	};
});

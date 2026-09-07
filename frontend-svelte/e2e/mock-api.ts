/**
 * Stand-in for FastAPI so end-to-end tests walk the real sign-in path without
 * the full stack. Started by playwright.config.ts. Mirrors the contracts in
 * backend/app/api/routes/v1/{auth,token}.py.
 */
import { CREDENTIALS, DEVELOPER, PROVIDER_SETTINGS, makeUsers } from './fixtures';

// Mutable: the write endpoints change it, and /__reset restores it between tests.
let USERS = makeUsers();

const PORT = Number(process.env.MOCK_API_PORT ?? 8787);

let issued = 0;
const validAccessTokens = new Set<string>();
const validRefreshTokens = new Set<string>();

function issueTokens() {
	issued += 1;
	const access = `access-${issued}`;
	const refresh = `rt-${issued}`;
	validAccessTokens.add(access);
	validRefreshTokens.add(refresh);
	return { access_token: access, token_type: 'bearer', refresh_token: refresh, expires_in: 3600 };
}

const json = (body: unknown, status = 200) =>
	new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } });

const server = Bun.serve({
	port: PORT,
	async fetch(request) {
		const { pathname } = new URL(request.url);

		if (pathname === '/__reset') {
			USERS = makeUsers();
			return new Response(null, { status: 204 });
		}

		if (pathname === '/api/v1/auth/login') {
			const form = await request.formData();
			const ok =
				form.get('username') === CREDENTIALS.email && form.get('password') === CREDENTIALS.password;
			return ok ? json(issueTokens()) : json({ detail: 'Incorrect email or password' }, 401);
		}

		if (pathname === '/api/v1/auth/me') {
			const token = request.headers.get('authorization')?.replace('Bearer ', '') ?? '';
			return validAccessTokens.has(token) ? json(DEVELOPER) : json({ detail: 'Unauthorized' }, 401);
		}

		if (pathname === '/api/v1/oauth/providers') {
			return json(PROVIDER_SETTINGS);
		}

		if (pathname === '/api/v1/users' && request.method === 'POST') {
			const body = await request.json();
			if (USERS.some((user) => body.email && user.email === body.email)) {
				return json({ detail: 'User with this email already exists.' }, 409);
			}
			const created = {
				id: `00000000-0000-4000-8000-${String(USERS.length + 1).padStart(12, '0')}`,
				created_at: new Date().toISOString(),
				first_name: body.first_name ?? null,
				last_name: body.last_name ?? null,
				email: body.email ?? null,
				last_synced_at: null,
				last_synced_provider: null,
				has_active_connection: false,
				connections: []
			};
			USERS.unshift(created);
			return json(created, 201);
		}

		const userMatch = pathname.match(/^\/api\/v1\/users\/([^/]+)$/);
		if (userMatch && request.method !== 'GET') {
			const index = USERS.findIndex((user) => user.id === userMatch[1]);
			if (index === -1) return json({ detail: 'Not found' }, 404);

			if (request.method === 'DELETE') return json(USERS.splice(index, 1)[0]);

			const body = await request.json();
			if (body.email && USERS.some((user, i) => i !== index && user.email === body.email)) {
				return json({ detail: 'User with this email already exists.' }, 409);
			}
			Object.assign(USERS[index], {
				first_name: body.first_name ?? null,
				last_name: body.last_name ?? null,
				email: body.email ?? null
			});
			return json(USERS[index]);
		}

		if (pathname === '/api/v1/users') {
			const params = new URL(request.url).searchParams;
			const search = params.get('search')?.toLowerCase() ?? '';
			const page = Number(params.get('page') ?? 1);
			const limit = Number(params.get('limit') ?? 20);
			const includeConnections = params.getAll('include').includes('connections');

			const wantedProviders = params.getAll('provider');

			let matched = USERS.filter((user) => {
				if (
					search &&
					![user.first_name, user.last_name, user.email, user.id]
						.join(' ')
						.toLowerCase()
						.includes(search)
				) {
					return false;
				}
				if (
					wantedProviders.length > 0 &&
					!user.connections.some((c) => wantedProviders.includes(c.provider))
				) {
					return false;
				}
				return true;
			});

			const direction = params.get('sort_order') === 'asc' ? 1 : -1;
			const key = params.get('sort_by') ?? 'created_at';
			matched = [...matched].sort((a, b) => {
				const left = key === 'name' ? `${a.first_name} ${a.last_name}` : String(a[key] ?? '');
				const right = key === 'name' ? `${b.first_name} ${b.last_name}` : String(b[key] ?? '');
				return left.localeCompare(right) * direction;
			});

			const items = matched.slice((page - 1) * limit, page * limit).map((user) => ({
				...user,
				connections: includeConnections ? user.connections : null
			}));

			return json({
				items,
				total: matched.length,
				page,
				limit,
				pages: Math.ceil(matched.length / limit),
				has_next: page * limit < matched.length,
				has_prev: page > 1
			});
		}

		if (pathname === '/api/v1/token/refresh') {
			const { refresh_token } = await request.json();
			if (!validRefreshTokens.has(refresh_token)) return json({ detail: 'Invalid' }, 401);
			// The real backend rotates: the old token stops working.
			validRefreshTokens.delete(refresh_token);
			return json(issueTokens());
		}

		if (pathname === '/api/v1/token/revoke') {
			const { refresh_token } = await request.json();
			validRefreshTokens.delete(refresh_token);
			return new Response(null, { status: 204 });
		}

		return json({ detail: 'Not found' }, 404);
	}
});

console.log(`mock api listening on ${server.url}`);

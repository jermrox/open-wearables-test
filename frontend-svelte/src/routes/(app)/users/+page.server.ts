import { redirect } from '@sveltejs/kit';
import { resolve } from '$app/paths';
import { fetchProviders } from '$lib/server/providers';
import { fetchUsers } from '$lib/server/users';
import { parseUsersQuery, usersQueryHref, withUsersQuery } from '$lib/users/query';
import type { PageServerLoad } from './$types';

export const load: PageServerLoad = async ({ url, locals }) => {
	// Loads run concurrently with the layout guard, so this cannot assume it ran.
	const accessToken = await locals.auth.accessToken();
	if (!accessToken) redirect(303, resolve('/login'));

	const query = parseUsersQuery(url.searchParams);
	const [users, providers] = await Promise.all([
		fetchUsers(query, accessToken),
		fetchProviders(accessToken)
	]);

	// A stale deep link, or a page-size change made against a total that has
	// since shrunk, would otherwise render a dead empty page.
	if (users.total > 0 && query.page > users.pages) {
		redirect(303, usersQueryHref(withUsersQuery(query, { page: users.pages })));
	}

	return { query, users, providers };
};

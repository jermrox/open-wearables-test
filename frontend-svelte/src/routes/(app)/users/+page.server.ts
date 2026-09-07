import { fail, redirect } from '@sveltejs/kit';
import { resolve } from '$app/paths';
import { ApiError } from '$lib/server/api';
import { fetchProviders } from '$lib/server/providers';
import { createUser, deleteUser, fetchUsers, updateUser, type UserInput } from '$lib/server/users';
import { parseUsersQuery, usersQueryHref, withUsersQuery } from '$lib/users/query';
import type { Actions, PageServerLoad } from './$types';

/** Loads and actions run concurrently with the layout guard, so neither can
 *  assume it ran. */
async function requireToken(locals: App.Locals): Promise<string> {
	const accessToken = await locals.auth.accessToken();
	if (!accessToken) redirect(303, resolve('/login'));
	return accessToken;
}

export const load: PageServerLoad = async ({ url, locals }) => {
	const accessToken = await requireToken(locals);

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

function readInput(form: FormData): UserInput {
	const field = (name: string) => String(form.get(name) ?? '').trim() || undefined;
	return { first_name: field('first_name'), last_name: field('last_name'), email: field('email') };
}

/** Echoes the submitted values back so a rejected form keeps what was typed. */
async function attempt<T extends Record<string, unknown>>(
	action: string,
	context: T,
	work: () => Promise<unknown>
) {
	try {
		await work();
	} catch (error) {
		return fail(400, { action, ...context, message: describe(error) });
	}
	return { action };
}

function describe(error: unknown): string {
	if (!(error instanceof ApiError)) return 'Something went wrong. Try again.';
	if (error.status === 409) return 'A user with that email already exists.';
	if (error.status === 404) return 'That user no longer exists.';
	return error.message;
}

export const actions: Actions = {
	create: async ({ request, locals }) => {
		const accessToken = await requireToken(locals);
		const input = readInput(await request.formData());

		if (!input.first_name && !input.last_name && !input.email) {
			return fail(400, { action: 'create', ...input, message: 'Enter a name or an email.' });
		}
		return attempt('create', input, () => createUser(input, accessToken));
	},

	update: async ({ request, locals }) => {
		const accessToken = await requireToken(locals);
		const form = await request.formData();
		const id = String(form.get('id') ?? '');
		const input = readInput(form);

		return attempt('update', { id, ...input }, () => updateUser(id, input, accessToken));
	},

	delete: async ({ request, locals }) => {
		const accessToken = await requireToken(locals);
		const id = String((await request.formData()).get('id') ?? '');

		return attempt('delete', { id }, () => deleteUser(id, accessToken));
	}
};

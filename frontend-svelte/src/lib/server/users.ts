import { apiDelete, apiGet, apiPatch, apiPost } from './api';
import type { UsersQuery } from '$lib/users/query';
import type { PaginatedUsers, User } from '$lib/users/types';

export async function fetchUsers(query: UsersQuery, accessToken: string): Promise<PaginatedUsers> {
	const params = new URLSearchParams({
		page: String(query.page),
		limit: String(query.size),
		sort_by: query.sort,
		sort_order: query.order,
		include: 'connections'
	});

	if (query.search) params.set('search', query.search);
	for (const provider of query.providers) params.append('provider', provider);

	return apiGet<PaginatedUsers>(`/api/v1/users?${params}`, accessToken);
}

/** Empty strings are omitted: the API treats null as "unset", "" as a value. */
export type UserInput = {
	first_name?: string;
	last_name?: string;
	email?: string;
};

export const createUser = (input: UserInput, accessToken: string) =>
	apiPost<User>('/api/v1/users', accessToken, input);

export const updateUser = (id: string, input: UserInput, accessToken: string) =>
	apiPatch<User>(`/api/v1/users/${id}`, accessToken, input);

export const deleteUser = (id: string, accessToken: string) =>
	apiDelete<User>(`/api/v1/users/${id}`, accessToken);

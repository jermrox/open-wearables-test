import { apiGet } from './api';
import type { UsersQuery } from '$lib/users/query';
import type { PaginatedUsers } from '$lib/users/types';

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

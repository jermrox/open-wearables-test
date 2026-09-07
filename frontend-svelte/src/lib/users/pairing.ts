/** The page an end user opens to connect a provider; lives on this frontend. */
export function pairingPath(userId: string): string {
	return `/users/${userId}/pair`;
}

export function pairingLink(origin: string, userId: string): string {
	return `${origin.replace(/\/+$/, '')}${pairingPath(userId)}`;
}

import type { AuthContext } from '$lib/server/auth';

declare global {
	namespace App {
		interface Locals {
			auth: AuthContext;
		}
	}
}

export {};

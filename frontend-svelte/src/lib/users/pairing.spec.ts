import { describe, expect, it } from 'vitest';
import { pairingLink } from './pairing';

describe('pairingLink', () => {
	it('builds an absolute link an admin can paste into a message', () => {
		expect(pairingLink('https://app.example.com', 'abc-123')).toBe(
			'https://app.example.com/users/abc-123/pair'
		);
	});

	// origin from a proxy or config sometimes arrives with a trailing slash.
	it('does not double the slash', () => {
		expect(pairingLink('https://app.example.com/', 'abc-123')).toBe(
			'https://app.example.com/users/abc-123/pair'
		);
	});
});

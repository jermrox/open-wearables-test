import type { SubmitFunction } from '@sveltejs/kit';

/**
 * Shared submit behaviour for the dialog forms: track submission, close on
 * success, and never reset — the fields are bound to local state, and a failed
 * submit must keep what was typed.
 */
export function createDialogSubmit(close: () => void) {
	let submitting = $state(false);

	const enhance: SubmitFunction = () => {
		submitting = true;
		return async ({ result, update }) => {
			submitting = false;
			if (result.type === 'success') close();
			await update({ reset: false });
		};
	};

	return {
		get submitting() {
			return submitting;
		},
		enhance
	};
}

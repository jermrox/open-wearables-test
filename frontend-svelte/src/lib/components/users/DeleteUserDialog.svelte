<script lang="ts">
	import { enhance } from '$app/forms';
	import Alert from '$lib/components/ui/Alert.svelte';
	import Button from '$lib/components/ui/Button.svelte';
	import Sheet from '$lib/components/ui/Sheet.svelte';
	import { fullName } from '$lib/users/avatar';
	import type { User } from '$lib/users/types';
	import { createDialogSubmit } from '$lib/utils/forms.svelte';

	let {
		open = $bindable(false),
		user,
		message
	}: { open?: boolean; user: User | null; message?: string } = $props();

	const submit = createDialogSubmit(() => (open = false));

	const who = $derived(user ? fullName(user) || user.email || 'this user' : '');
</script>

<Sheet bind:open title="Delete user">
	{#if user}
		<form
			method="POST"
			action="?/delete"
			class="flex flex-col gap-4 px-4 pb-2"
			use:enhance={submit.enhance}
		>
			<input type="hidden" name="id" value={user.id} />

			{#if message}
				<Alert>{message}</Alert>
			{/if}

			<p class="text-sm">
				Delete <span class="font-medium">{who}</span>? Their synced data goes with them and this
				cannot be undone.
			</p>

			<div class="mt-1 flex justify-end gap-2">
				<Button variant="outline" onclick={() => (open = false)}>Cancel</Button>
				<Button
					type="submit"
					disabled={submit.submitting}
					class="bg-danger text-danger-foreground hover:bg-danger/90"
				>
					{submit.submitting ? 'Deleting…' : 'Delete user'}
				</Button>
			</div>
		</form>
	{/if}
</Sheet>

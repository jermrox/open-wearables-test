<script lang="ts">
	import Link2 from '@lucide/svelte/icons/link-2';
	import Pencil from '@lucide/svelte/icons/pencil';
	import Trash2 from '@lucide/svelte/icons/trash-2';
	import { fullName } from '$lib/users/avatar';
	import type { User } from '$lib/users/types';

	let { user }: { user: User } = $props();

	const who = $derived(fullName(user) || user.email || 'this user');

	const base =
		'grid size-8 place-items-center rounded-lg border border-transparent transition-colors disabled:cursor-not-allowed disabled:opacity-40';
</script>

<!-- z-10 keeps these above the row-wide overlay link in UserIdentity, so a
     click here does not also open the user. -->
<div class="relative z-10 flex items-center justify-end gap-0.5">
	<button
		type="button"
		disabled
		title="Editing user details is not built yet"
		aria-label="Edit {who}"
		class="{base} text-muted-foreground hover:bg-surface-muted hover:text-foreground"
	>
		<Pencil size={15} aria-hidden="true" />
	</button>
	<button
		type="button"
		disabled
		title="The pairing page is not built yet, so the link would not resolve"
		aria-label="Copy pairing link for {who}"
		class="{base} text-muted-foreground hover:bg-surface-muted hover:text-foreground"
	>
		<Link2 size={15} aria-hidden="true" />
	</button>
	<button
		type="button"
		disabled
		title="Deleting users is not built yet"
		aria-label="Delete {who}"
		class="{base} text-muted-foreground hover:bg-danger/10 hover:text-danger"
	>
		<Trash2 size={15} aria-hidden="true" />
	</button>
</div>

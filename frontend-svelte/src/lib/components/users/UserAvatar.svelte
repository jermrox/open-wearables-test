<script lang="ts">
	import { avatarTone, initials } from '$lib/users/avatar';
	import { cn } from '$lib/utils/cn';
	import type { User } from '$lib/users/types';

	let { user }: { user: User } = $props();
</script>

<span
	aria-hidden="true"
	class={cn(
		'grid size-9 shrink-0 place-items-center rounded-full text-xs font-semibold',
		avatarTone(user.id)
	)}
>
	{initials(user)}
</span>

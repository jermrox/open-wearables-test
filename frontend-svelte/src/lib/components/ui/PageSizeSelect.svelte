<script lang="ts">
	import ChevronDown from '@lucide/svelte/icons/chevron-down';
	import { goto } from '$app/navigation';
	import { PAGE_SIZES, isPageSize, type PageSize } from '$lib/lists/pagination';

	let { size, hrefFor }: { size: number; hrefFor: (size: PageSize) => string } = $props();

	// The same bar renders above and below the list, so the id cannot be fixed.
	const id = $props.id();
</script>

<!-- A native select rather than a row of links: it collapses to one control on
     a phone and hands over to the OS picker. Unlike the pager links this one
     does need JS, which is the trade for the space it saves. -->
<div class="relative inline-flex items-center">
	<label class="sr-only text-xs text-muted-foreground/70 sm:not-sr-only sm:mr-1.5" for={id}>
		Per page
	</label>
	<select
		{id}
		value={size}
		onchange={(event) => {
			const next = Number(event.currentTarget.value);
			// eslint-disable-next-line svelte/no-navigation-without-resolve -- hrefFor resolves
			if (isPageSize(next)) goto(hrefFor(next));
		}}
		class="h-8 appearance-none rounded-md border border-border bg-surface pr-7 pl-2
			text-xs text-foreground tabular-nums"
	>
		{#each PAGE_SIZES as option (option)}
			<option value={option}>{option}</option>
		{/each}
	</select>
	<ChevronDown
		size={13}
		aria-hidden="true"
		class="pointer-events-none absolute right-2 text-muted-foreground"
	/>
</div>

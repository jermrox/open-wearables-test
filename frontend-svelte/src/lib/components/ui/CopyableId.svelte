<script lang="ts">
	import Check from '@lucide/svelte/icons/check';
	import Copy from '@lucide/svelte/icons/copy';

	let {
		value,
		label = 'ID',
		visible = 4
	}: { value: string; label?: string; visible?: number } = $props();

	const RESET_MS = 2000;

	let copied = $state(false);
	let timer: ReturnType<typeof setTimeout> | undefined;

	$effect(() => () => clearTimeout(timer));

	async function copy() {
		try {
			await navigator.clipboard.writeText(value);
			copied = true;
			clearTimeout(timer);
			timer = setTimeout(() => (copied = false), RESET_MS);
		} catch {
			// Clipboard access can be denied; the full value is in the title either way.
		}
	}
</script>

<span class="relative z-10 inline-flex items-center gap-1">
	<code
		title={value}
		class="rounded bg-surface-muted px-1.5 py-0.5 font-mono text-xs text-foreground/80"
	>
		{value.slice(0, visible)}…
	</code>
	<button
		type="button"
		onclick={copy}
		aria-label={copied ? `${label} copied` : `Copy ${label}`}
		class="grid size-7 place-items-center rounded text-muted-foreground transition-colors
			hover:text-foreground"
	>
		{#if copied}
			<Check size={13} aria-hidden="true" class="text-success" />
		{:else}
			<Copy size={13} aria-hidden="true" />
		{/if}
	</button>
</span>

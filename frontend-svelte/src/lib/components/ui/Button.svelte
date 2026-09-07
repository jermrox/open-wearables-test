<script lang="ts">
	import type { Snippet } from 'svelte';
	import type { HTMLButtonAttributes } from 'svelte/elements';
	import { cn } from '$lib/utils/cn';

	let {
		variant = 'primary',
		type = 'button',
		class: className,
		children,
		...rest
	}: HTMLButtonAttributes & {
		variant?: 'primary' | 'outline';
		children: Snippet;
	} = $props();

	const VARIANT = {
		primary: 'bg-primary text-primary-foreground hover:bg-primary-hover',
		outline: 'border border-border hover:bg-surface-muted'
	} as const;
</script>

<!-- Spreads the rest so callers keep control of aria-* and the like. -->
<button
	{type}
	{...rest}
	class={cn(
		'inline-flex min-h-11 items-center justify-center gap-2 rounded-lg px-4 text-sm font-medium whitespace-nowrap transition-colors disabled:opacity-50',
		VARIANT[variant],
		className
	)}
>
	{@render children()}
</button>

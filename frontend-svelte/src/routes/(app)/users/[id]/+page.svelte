<script lang="ts">
	import PagePlaceholder from '$lib/components/PagePlaceholder.svelte';
	import type { PageData } from './$types';

	let { data }: { data: PageData } = $props();
</script>

<PagePlaceholder title="User {data.id}" />

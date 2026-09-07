<script lang="ts">
	import UserPlus from '@lucide/svelte/icons/user-plus';
	import Button from '$lib/components/ui/Button.svelte';
</script>

<!-- Disabled rather than silently inert: the slot is reserved, and a control
     that looks live but does nothing is worse than one that says so. -->
<Button disabled title="Creating users is not built yet" class="w-full">
	<UserPlus size={16} aria-hidden="true" />
	Add user
</Button>

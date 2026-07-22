<script lang="ts">
	import { createEventDispatcher, getContext } from 'svelte';

	import { buildGroupMap, formatRunTimestamp, getSourceScopeLabel } from './utils';
	import type { AutoKnowledgeJob } from './types';

	const dispatch = createEventDispatcher<{
		select: { jobId: string };
		run: { jobId: string };
		toggle: { job: AutoKnowledgeJob };
		edit: { job: AutoKnowledgeJob };
		delete: { job: AutoKnowledgeJob };
		refresh: undefined;
	}>();

	const i18n: any = getContext('i18n');

	export let jobs: AutoKnowledgeJob[] = [];
	export let loading = false;
	export let selectedJobId = '';
	export let groups: { id: string; name: string }[] = [];

	$: groupsById = buildGroupMap(groups);
</script>

<section
	class="rounded-2xl border border-gray-100 bg-white p-4 dark:border-gray-850 dark:bg-gray-900"
>
	<div class="mb-3 flex items-center justify-between gap-3">
		<div>
			<div class="text-sm font-semibold text-gray-900 dark:text-gray-100">{$i18n.t('Jobs')}</div>
			<div class="text-xs text-gray-500 dark:text-gray-400">
				{jobs.length}
				{$i18n.t('configured')}
			</div>
		</div>
		<button
			class="text-xs text-gray-500 hover:text-gray-900 dark:hover:text-gray-100"
			on:click={() => dispatch('refresh')}
		>
			{$i18n.t('Refresh')}
		</button>
	</div>

	{#if loading}
		<div class="text-sm text-gray-500 dark:text-gray-400">{$i18n.t('Loading...')}</div>
	{:else if jobs.length === 0}
		<div class="text-sm text-gray-500 dark:text-gray-400">
			{$i18n.t('No Auto Knowledge jobs yet.')}
		</div>
	{:else}
		<div class="space-y-2">
			{#each jobs as job}
				<div
					class={`w-full rounded-xl border px-3 py-3 text-left transition ${
						selectedJobId === job.id
							? 'border-gray-900 bg-gray-50 dark:border-gray-200 dark:bg-gray-850'
							: 'border-gray-100 hover:border-gray-200 dark:border-gray-850 dark:hover:border-gray-700'
					}`}
					role="button"
					tabindex="0"
					on:click={() => dispatch('select', { jobId: job.id })}
					on:keydown={(event) => {
						if (event.key === 'Enter' || event.key === ' ') {
							event.preventDefault();
							dispatch('select', { jobId: job.id });
						}
					}}
				>
					<div class="flex items-start justify-between gap-3">
						<div class="min-w-0">
							<div class="truncate text-sm font-medium text-gray-900 dark:text-gray-100">
								{job.name}
							</div>
							<div class="mt-1 text-xs text-gray-500 dark:text-gray-400">
								{job.is_active ? $i18n.t('Active') : $i18n.t('Paused')}
								{#if job.is_running}
									· {$i18n.t('Running')}
								{/if}
							</div>
							<div class="mt-1 line-clamp-2 text-xs text-gray-400 dark:text-gray-500">
								{getSourceScopeLabel(job, groupsById)}
							</div>
						</div>
						<div class="text-right text-xs text-gray-500 dark:text-gray-400">
							<div>{$i18n.t('Next Run')}</div>
							<div>{formatRunTimestamp(job.next_run_at)}</div>
						</div>
					</div>

					<div class="mt-3 flex flex-wrap gap-2 text-xs">
						<button
							class="rounded-lg border border-gray-200 px-2 py-1 dark:border-gray-800"
							on:click|stopPropagation={() => dispatch('run', { jobId: job.id })}
						>
							{$i18n.t('Run')}
						</button>
						<button
							class="rounded-lg border border-gray-200 px-2 py-1 dark:border-gray-800"
							on:click|stopPropagation={() => dispatch('edit', { job })}
						>
							{$i18n.t('Edit')}
						</button>
						<button
							class="rounded-lg border border-gray-200 px-2 py-1 dark:border-gray-800"
							on:click|stopPropagation={() => dispatch('toggle', { job })}
						>
							{job.is_active ? $i18n.t('Pause') : $i18n.t('Resume')}
						</button>
						<button
							class="rounded-lg border border-gray-200 px-2 py-1 text-red-500 dark:border-gray-800"
							on:click|stopPropagation={() => dispatch('delete', { job })}
						>
							{$i18n.t('Delete')}
						</button>
					</div>
				</div>
			{/each}
		</div>
	{/if}
</section>

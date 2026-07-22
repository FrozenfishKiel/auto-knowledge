<script lang="ts">
	import { getContext } from 'svelte';

	import type { AutoKnowledgeRun } from './types';
	import { formatDuration, formatRunTimestamp, getRunSummary } from './utils';

	const i18n: any = getContext('i18n');

	export let runs: AutoKnowledgeRun[] = [];
	export let selectedJobName = '';
</script>

<section
	class="rounded-2xl border border-gray-100 bg-white p-4 dark:border-gray-850 dark:bg-gray-900"
>
	<div class="mb-3 flex items-end justify-between gap-3">
		<div>
			<div class="text-sm font-semibold text-gray-900 dark:text-gray-100">
				{$i18n.t('Run History')}
			</div>
			<div class="text-xs text-gray-500 dark:text-gray-400">
				{selectedJobName || $i18n.t('Select a job')}
			</div>
		</div>
	</div>

	{#if runs.length === 0}
		<div class="text-sm text-gray-500 dark:text-gray-400">{$i18n.t('No runs yet.')}</div>
	{:else}
		<div class="overflow-x-auto">
			<table class="w-full text-sm">
				<thead class="text-left text-xs text-gray-500 dark:text-gray-400">
					<tr class="border-b border-gray-100 dark:border-gray-850">
						<th class="pb-2 font-medium">{$i18n.t('Status')}</th>
						<th class="pb-2 font-medium">{$i18n.t('Started')}</th>
						<th class="pb-2 font-medium">{$i18n.t('Duration')}</th>
						<th class="pb-2 font-medium">{$i18n.t('Counts')}</th>
						<th class="pb-2 font-medium">{$i18n.t('Error')}</th>
					</tr>
				</thead>
				<tbody>
					{#each runs as run}
						<tr class="border-b border-gray-50 align-top dark:border-gray-900">
							<td class="py-2 text-gray-900 dark:text-gray-100">{run.status}</td>
							<td class="py-2 text-gray-600 dark:text-gray-300"
								>{formatRunTimestamp(run.started_at)}</td
							>
							<td class="py-2 text-gray-600 dark:text-gray-300"
								>{formatDuration(run.started_at, run.finished_at)}</td
							>
							<td class="py-2 text-xs text-gray-600 dark:text-gray-300">
								{run.input_count}/
								{run.cleaned_count}/
								{run.generated_count}/
								{run.published_count}
							</td>
							<td
								class={`py-2 text-xs ${run.error ? 'text-red-500' : 'text-gray-500 dark:text-gray-400'}`}
							>
								{getRunSummary(run)}
							</td>
						</tr>
					{/each}
				</tbody>
			</table>
		</div>
	{/if}
</section>

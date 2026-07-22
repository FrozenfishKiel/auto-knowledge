<script lang="ts">
	import { createEventDispatcher, getContext } from 'svelte';

	import type { AutoKnowledgeCandidate, AutoKnowledgeJob } from './types';
	import { getSourceSummary } from './utils';

	const dispatch = createEventDispatcher<{
		select: { candidate: AutoKnowledgeCandidate };
	}>();

	const i18n: any = getContext('i18n');

	export let candidates: AutoKnowledgeCandidate[] = [];
	export let jobs: AutoKnowledgeJob[] = [];
	export let selectedCandidateId = '';
	export let filters = {
		jobId: '',
		status: '',
		riskLevel: '',
		query: ''
	};
</script>

<section
	class="rounded-2xl border border-gray-100 bg-white p-4 dark:border-gray-850 dark:bg-gray-900"
>
	<div class="mb-3 flex items-center justify-between gap-3">
		<div>
			<div class="text-sm font-semibold text-gray-900 dark:text-gray-100">
				{$i18n.t('Review Queue')}
			</div>
			<div class="text-xs text-gray-500 dark:text-gray-400">
				{candidates.length}
				{$i18n.t('candidates')}
			</div>
		</div>
	</div>

	<div class="mb-4 grid grid-cols-1 gap-2 md:grid-cols-4">
		<select
			class="rounded-xl border border-gray-200 bg-transparent px-3 py-2 text-sm dark:border-gray-800"
			bind:value={filters.jobId}
		>
			<option value="">{$i18n.t('All Jobs')}</option>
			{#each jobs as job}
				<option value={job.id}>{job.name}</option>
			{/each}
		</select>

		<select
			class="rounded-xl border border-gray-200 bg-transparent px-3 py-2 text-sm dark:border-gray-800"
			bind:value={filters.status}
		>
			<option value="">{$i18n.t('All Statuses')}</option>
			<option value="pending_review">{$i18n.t('pending_review')}</option>
			<option value="approved">{$i18n.t('approved')}</option>
			<option value="published">{$i18n.t('published')}</option>
			<option value="rejected">{$i18n.t('rejected')}</option>
			<option value="publish_failed">{$i18n.t('publish_failed')}</option>
		</select>

		<select
			class="rounded-xl border border-gray-200 bg-transparent px-3 py-2 text-sm dark:border-gray-800"
			bind:value={filters.riskLevel}
		>
			<option value="">{$i18n.t('All Risk Levels')}</option>
			<option value="low">{$i18n.t('low')}</option>
			<option value="medium">{$i18n.t('medium')}</option>
			<option value="high">{$i18n.t('high')}</option>
		</select>

		<input
			class="rounded-xl border border-gray-200 bg-transparent px-3 py-2 text-sm dark:border-gray-800"
			placeholder={$i18n.t('Search candidates')}
			bind:value={filters.query}
		/>
	</div>

	{#if candidates.length === 0}
		<div class="text-sm text-gray-500 dark:text-gray-400">
			{$i18n.t('No candidates to review.')}
		</div>
	{:else}
		<div class="grid grid-cols-1 gap-3 xl:grid-cols-2">
			{#each candidates as candidate}
				<button
					class={`rounded-xl border p-3 text-left transition ${
						selectedCandidateId === candidate.id
							? 'border-gray-900 bg-gray-50 dark:border-gray-200 dark:bg-gray-850'
							: 'border-gray-100 hover:border-gray-200 dark:border-gray-850 dark:hover:border-gray-700'
					}`}
					on:click={() => dispatch('select', { candidate })}
				>
					<div class="mb-1 line-clamp-2 text-sm font-medium text-gray-900 dark:text-gray-100">
						{candidate.question}
					</div>
					<div class="line-clamp-3 text-sm text-gray-600 dark:text-gray-300">
						{candidate.answer}
					</div>

					<div class="mt-3 flex flex-wrap gap-2 text-xs text-gray-500 dark:text-gray-400">
						<span>{candidate.status}</span>
						<span>{candidate.confidence}%</span>
						<span>{candidate.risk_level}</span>
						{#each getSourceSummary(candidate) as item}
							<span>{item}</span>
						{/each}
					</div>
				</button>
			{/each}
		</div>
	{/if}
</section>

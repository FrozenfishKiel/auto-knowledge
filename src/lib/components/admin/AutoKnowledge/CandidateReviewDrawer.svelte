<script lang="ts">
	import { createEventDispatcher, getContext } from 'svelte';

	import type { AutoKnowledgeCandidateDetail } from './types';
	import type { ReviewDraft } from './utils';
	import { getAvailableCandidateActions, getSourcePreviewItems, getSourceSummary } from './utils';

	const dispatch = createEventDispatcher<{
		close: undefined;
		approve: undefined;
		approvePublish: undefined;
		reject: undefined;
		publish: undefined;
	}>();

	const i18n: any = getContext('i18n');

	export let open = false;
	export let candidate: AutoKnowledgeCandidateDetail | null = null;
	export let draft: ReviewDraft | null = null;
	export let saving = false;
</script>

{#if open && candidate && draft}
	<button
		type="button"
		class="fixed inset-0 z-40 bg-black/30"
		aria-label={$i18n.t('Close')}
		on:click={() => dispatch('close')}
	></button>
	<aside
		class="fixed right-0 top-0 z-50 h-full w-full max-w-2xl overflow-y-auto border-l border-gray-200 bg-white p-5 shadow-2xl dark:border-gray-800 dark:bg-gray-950"
	>
		<div class="mb-4 flex items-start justify-between gap-4">
			<div>
				<div class="text-lg font-semibold text-gray-900 dark:text-gray-100">
					{$i18n.t('Candidate Review')}
				</div>
				<div class="mt-1 flex flex-wrap gap-2 text-xs text-gray-500 dark:text-gray-400">
					<span>{candidate.status}</span>
					<span>{candidate.confidence}%</span>
					<span>{candidate.risk_level}</span>
					{#each getSourceSummary(candidate) as item}
						<span>{item}</span>
					{/each}
				</div>
			</div>

			<button
				class="rounded-lg border border-gray-200 px-2 py-1 text-xs dark:border-gray-800"
				on:click={() => dispatch('close')}
			>
				{$i18n.t('Close')}
			</button>
		</div>

		<div class="grid grid-cols-1 gap-3 text-sm">
			<div>
				<div class="mb-1 text-xs text-gray-500 dark:text-gray-400">{$i18n.t('Question')}</div>
				<textarea
					class="min-h-24 w-full rounded-xl border border-gray-200 bg-transparent px-3 py-2 dark:border-gray-800"
					bind:value={draft.question}
				></textarea>
			</div>

			<div>
				<div class="mb-1 text-xs text-gray-500 dark:text-gray-400">{$i18n.t('Answer')}</div>
				<textarea
					class="min-h-40 w-full rounded-xl border border-gray-200 bg-transparent px-3 py-2 dark:border-gray-800"
					bind:value={draft.answer}
				></textarea>
			</div>

			<div class="grid grid-cols-1 gap-3 md:grid-cols-2">
				<div>
					<div class="mb-1 text-xs text-gray-500 dark:text-gray-400">{$i18n.t('Category')}</div>
					<input
						class="w-full rounded-xl border border-gray-200 bg-transparent px-3 py-2 dark:border-gray-800"
						bind:value={draft.category}
					/>
				</div>

				<div>
					<div class="mb-1 text-xs text-gray-500 dark:text-gray-400">{$i18n.t('Tags')}</div>
					<input
						class="w-full rounded-xl border border-gray-200 bg-transparent px-3 py-2 dark:border-gray-800"
						bind:value={draft.tagsText}
					/>
				</div>
			</div>

			<div>
				<div class="mb-1 text-xs text-gray-500 dark:text-gray-400">
					{$i18n.t('Rejection Reason')}
				</div>
				<textarea
					class="min-h-20 w-full rounded-xl border border-gray-200 bg-transparent px-3 py-2 dark:border-gray-800"
					bind:value={draft.rejectionReason}
				></textarea>
			</div>

			<div
				class="rounded-xl border border-gray-200 p-3 text-xs text-gray-500 dark:border-gray-800 dark:text-gray-400"
			>
				<div class="mb-2 font-medium text-gray-700 dark:text-gray-200">{$i18n.t('Metadata')}</div>
				<pre class="overflow-x-auto whitespace-pre-wrap break-all">{JSON.stringify(
						candidate.meta ?? {},
						null,
						2
					)}</pre>
			</div>

			<div
				class="rounded-xl border border-gray-200 p-3 text-xs text-gray-500 dark:border-gray-800 dark:text-gray-400"
			>
				<div class="mb-2 font-medium text-gray-700 dark:text-gray-200">{$i18n.t('Sources')}</div>
				{#if candidate.sources?.length}
					<div class="space-y-2">
						{#each getSourcePreviewItems(candidate) as source}
							<div class="rounded-lg border border-gray-100 p-2 dark:border-gray-900">
								<div
									class="mb-1 font-medium uppercase tracking-wide text-gray-700 dark:text-gray-200"
								>
									{source.title}
								</div>
								<div class="whitespace-pre-wrap break-words text-gray-600 dark:text-gray-300">
									{source.body}
								</div>
								<div class="mt-1 text-[11px] text-gray-400 dark:text-gray-500">{source.meta}</div>
							</div>
						{/each}
					</div>
				{:else}
					<div>{$i18n.t('No source preview available.')}</div>
				{/if}
			</div>

			<div class="flex flex-wrap gap-2 pt-2">
				{#if getAvailableCandidateActions(candidate).includes('approve')}
					<button
						class="rounded-xl border border-gray-200 px-3 py-2 text-sm dark:border-gray-800"
						disabled={saving}
						on:click={() => dispatch('approve')}
					>
						{$i18n.t('Approve')}
					</button>
				{/if}
				{#if getAvailableCandidateActions(candidate).includes('approve_publish')}
					<button
						class="rounded-xl bg-gray-900 px-3 py-2 text-sm text-white dark:bg-gray-100 dark:text-gray-900"
						disabled={saving}
						on:click={() => dispatch('approvePublish')}
					>
						{$i18n.t('Approve & Publish')}
					</button>
				{/if}
				{#if getAvailableCandidateActions(candidate).includes('reject')}
					<button
						class="rounded-xl border border-gray-200 px-3 py-2 text-sm text-red-500 dark:border-gray-800"
						disabled={saving}
						on:click={() => dispatch('reject')}
					>
						{$i18n.t('Reject')}
					</button>
				{/if}
				{#if getAvailableCandidateActions(candidate).includes('publish')}
					<button
						class="rounded-xl bg-gray-900 px-3 py-2 text-sm text-white dark:bg-gray-100 dark:text-gray-900"
						disabled={saving}
						on:click={() => dispatch('publish')}
					>
						{$i18n.t('Publish')}
					</button>
				{/if}
			</div>
		</div>
	</aside>
{/if}

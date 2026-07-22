<script lang="ts">
	import { createEventDispatcher, getContext } from 'svelte';

	import type {
		AutoKnowledgeGroup,
		AutoKnowledgeJobFormState,
		AutoKnowledgeKnowledgeBase
	} from './types';

	const dispatch = createEventDispatcher<{
		submit: undefined;
		cancelEdit: undefined;
	}>();

	const i18n: any = getContext('i18n');

	export let form: AutoKnowledgeJobFormState;
	export let groups: AutoKnowledgeGroup[] = [];
	export let knowledgeBases: AutoKnowledgeKnowledgeBase[] = [];
	export let saving = false;
	export let editing = false;

	const toggleGroup = (groupId: string) => {
		const current = new Set(form.source_filter.group_ids);
		if (current.has(groupId)) {
			current.delete(groupId);
		} else {
			current.add(groupId);
		}

		form = {
			...form,
			source_filter: {
				...form.source_filter,
				group_ids: [...current]
			}
		};
	};
</script>

<section
	class="rounded-2xl border border-gray-100 bg-white p-4 dark:border-gray-850 dark:bg-gray-900"
>
	<div class="mb-4 flex items-center justify-between gap-3">
		<div>
			<div class="text-sm font-semibold text-gray-900 dark:text-gray-100">
				{editing ? $i18n.t('Edit Job') : $i18n.t('New Job')}
			</div>
			<div class="text-xs text-gray-500 dark:text-gray-400">
				{editing
					? $i18n.t('Update schedule and source scope.')
					: $i18n.t('Create a scheduled knowledge mining job.')}
			</div>
		</div>

		{#if editing}
			<button
				class="rounded-lg border border-gray-200 px-2.5 py-1.5 text-xs font-medium text-gray-600 dark:border-gray-800 dark:text-gray-300"
				on:click={() => dispatch('cancelEdit')}
			>
				{$i18n.t('Cancel')}
			</button>
		{/if}
	</div>

	<div class="grid grid-cols-1 gap-3 text-sm">
		<input
			class="w-full rounded-xl border border-gray-200 bg-transparent px-3 py-2 dark:border-gray-800"
			placeholder={$i18n.t('Job name')}
			bind:value={form.name}
		/>

		<textarea
			class="min-h-24 w-full rounded-xl border border-gray-200 bg-transparent px-3 py-2 dark:border-gray-800"
			placeholder={$i18n.t('Description')}
			bind:value={form.description}
		></textarea>

		<select
			class="w-full rounded-xl border border-gray-200 bg-transparent px-3 py-2 dark:border-gray-800"
			bind:value={form.target_knowledge_id}
		>
			<option value="" disabled>{$i18n.t('Target knowledge base')}</option>
			{#each knowledgeBases as knowledge}
				<option value={knowledge.id}>{knowledge.name}</option>
			{/each}
		</select>

		<input
			class="w-full rounded-xl border border-gray-200 bg-transparent px-3 py-2 dark:border-gray-800"
			placeholder={$i18n.t('Extractor model ID')}
			bind:value={form.extractor.model_id}
		/>

		<div class="grid grid-cols-2 gap-2">
			<div>
				<div class="mb-1 text-xs text-gray-500 dark:text-gray-400">
					{$i18n.t('Lookback (hours)')}
				</div>
				<input
					class="w-full rounded-xl border border-gray-200 bg-transparent px-3 py-2 dark:border-gray-800"
					type="number"
					min="1"
					bind:value={form.source_filter.lookback_hours}
				/>
			</div>

			<div>
				<div class="mb-1 text-xs text-gray-500 dark:text-gray-400">{$i18n.t('Message limit')}</div>
				<input
					class="w-full rounded-xl border border-gray-200 bg-transparent px-3 py-2 dark:border-gray-800"
					type="number"
					min="1"
					bind:value={form.source_filter.limit}
				/>
			</div>
		</div>

		<div>
			<div class="mb-2 text-xs text-gray-500 dark:text-gray-400">{$i18n.t('Source groups')}</div>
			<div
				class="max-h-36 space-y-2 overflow-y-auto rounded-xl border border-gray-200 p-3 dark:border-gray-800"
			>
				{#if groups.length === 0}
					<div class="text-xs text-gray-500 dark:text-gray-400">
						{$i18n.t('No groups available.')}
					</div>
				{:else}
					{#each groups as group}
						<label
							class="flex items-center justify-between gap-3 text-xs text-gray-700 dark:text-gray-200"
						>
							<span class="truncate">{group.name}</span>
							<input
								type="checkbox"
								checked={form.source_filter.group_ids.includes(group.id)}
								on:change={() => toggleGroup(group.id)}
							/>
						</label>
					{/each}
				{/if}
			</div>
		</div>

		<div class="grid grid-cols-1 gap-2 md:grid-cols-2">
			<input
				class="w-full rounded-xl border border-gray-200 bg-transparent px-3 py-2 dark:border-gray-800"
				placeholder="RRULE:FREQ=DAILY;INTERVAL=1"
				bind:value={form.schedule.rrule}
			/>

			<input
				class="w-full rounded-xl border border-gray-200 bg-transparent px-3 py-2 dark:border-gray-800"
				placeholder={$i18n.t('Timezone')}
				bind:value={form.schedule.timezone}
			/>
		</div>

		<div
			class="flex items-center justify-between rounded-xl border border-gray-200 px-3 py-2 dark:border-gray-800"
		>
			<div>
				<div class="text-sm font-medium text-gray-900 dark:text-gray-100">{$i18n.t('Active')}</div>
				<div class="text-xs text-gray-500 dark:text-gray-400">
					{$i18n.t('Include this job in scheduled execution.')}
				</div>
			</div>
			<input type="checkbox" bind:checked={form.is_active} />
		</div>

		<button
			class="rounded-xl bg-gray-900 px-3 py-2 text-sm font-medium text-white hover:bg-gray-800 disabled:cursor-not-allowed disabled:opacity-60 dark:bg-gray-100 dark:text-gray-900"
			disabled={saving}
			on:click={() => dispatch('submit')}
		>
			{saving ? $i18n.t('Saving...') : editing ? $i18n.t('Save Changes') : $i18n.t('Create Job')}
		</button>
	</div>
</section>

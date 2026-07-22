<script lang="ts">
	import { getContext, onMount } from 'svelte';
	import { toast } from 'svelte-sonner';

	import {
		approveAutoKnowledgeCandidate,
		getAutoKnowledgeCandidate,
		createAutoKnowledgeJob,
		deleteAutoKnowledgeJob,
		getAutoKnowledgeCandidates,
		getAutoKnowledgeJobs,
		getAutoKnowledgeRuns,
		publishAutoKnowledgeCandidate,
		rejectAutoKnowledgeCandidate,
		runAutoKnowledgeJob,
		updateAutoKnowledgeJob
	} from '$lib/apis/auto-knowledge';
	import { getGroups } from '$lib/apis/groups';
	import { getKnowledgeBases } from '$lib/apis/knowledge';

	import CandidateList from './AutoKnowledge/CandidateList.svelte';
	import CandidateReviewDrawer from './AutoKnowledge/CandidateReviewDrawer.svelte';
	import RunHistory from './AutoKnowledge/RunHistory.svelte';
	import TaskEditor from './AutoKnowledge/TaskEditor.svelte';
	import TaskList from './AutoKnowledge/TaskList.svelte';
	import type {
		AutoKnowledgeCandidate,
		AutoKnowledgeCandidateDetail,
		AutoKnowledgeGroup,
		AutoKnowledgeJob,
		AutoKnowledgeJobFormState,
		AutoKnowledgeKnowledgeBase,
		AutoKnowledgeRun
	} from './AutoKnowledge/types';
	import {
		buildJobFormState,
		buildReviewDraft,
		filterCandidates,
		parseTagsText,
		type ReviewDraft
	} from './AutoKnowledge/utils';

	const i18n: any = getContext('i18n');

	const createEmptyForm = (): AutoKnowledgeJobFormState => ({
		name: '',
		description: '',
		target_knowledge_id: '',
		source_filter: {
			lookback_hours: 24,
			limit: 1000,
			group_ids: []
		},
		schedule: {
			rrule: 'RRULE:FREQ=DAILY;INTERVAL=1',
			timezone: Intl.DateTimeFormat().resolvedOptions().timeZone
		},
		extractor: { model_id: '' },
		review_policy: { mode: 'manual' },
		is_active: true
	});

	let loading = true;
	let savingJob = false;
	let savingCandidate = false;

	let jobs: AutoKnowledgeJob[] = [];
	let candidates: AutoKnowledgeCandidate[] = [];
	let runs: AutoKnowledgeRun[] = [];
	let groups: AutoKnowledgeGroup[] = [];
	let knowledgeBases: AutoKnowledgeKnowledgeBase[] = [];

	let selectedJobId = '';
	let selectedCandidate: AutoKnowledgeCandidateDetail | null = null;
	let selectedCandidateId = '';
	let reviewDraft: ReviewDraft | null = null;
	let editingJobId = '';

	let form = createEmptyForm();
	let candidateFilters = {
		jobId: '',
		status: '',
		riskLevel: '',
		query: ''
	};

	$: filteredCandidates = filterCandidates(candidates, candidateFilters);
	$: selectedJob = jobs.find((job) => job.id === selectedJobId) ?? null;
	$: selectedCandidateId = selectedCandidate?.id ?? '';

	const syncDefaultKnowledge = () => {
		if (!form.target_knowledge_id && knowledgeBases.length > 0) {
			form = {
				...form,
				target_knowledge_id: knowledgeBases[0].id
			};
		}
	};

	const refreshSelectedCandidate = async () => {
		if (!selectedCandidate) return;
		try {
			const detail = await getAutoKnowledgeCandidate(localStorage.token, selectedCandidate.id);
			selectedCandidate = detail;
			reviewDraft = buildReviewDraft(detail);
		} catch {
			selectedCandidate = null;
			reviewDraft = null;
		}
	};

	const load = async () => {
		loading = true;
		try {
			const [jobRes, candidateRes, knowledgeRes, groupRes] = await Promise.all([
				getAutoKnowledgeJobs(localStorage.token),
				getAutoKnowledgeCandidates(
					localStorage.token,
					candidateFilters.jobId || null,
					candidateFilters.status || null
				),
				getKnowledgeBases(localStorage.token),
				getGroups(localStorage.token)
			]);

			jobs = jobRes?.items ?? [];
			candidates = candidateRes?.items ?? [];
			knowledgeBases = knowledgeRes?.items ?? [];
			groups = groupRes ?? [];
			syncDefaultKnowledge();

			await refreshSelectedCandidate();
		} catch (error) {
			toast.error(`${error}`);
		} finally {
			loading = false;
		}
	};

	const loadRuns = async (jobId: string) => {
		selectedJobId = jobId;
		try {
			runs = await getAutoKnowledgeRuns(localStorage.token, jobId);
		} catch (error) {
			toast.error(`${error}`);
			runs = [];
		}
	};

	const resetForm = () => {
		const next = createEmptyForm();
		next.target_knowledge_id = form.target_knowledge_id || knowledgeBases[0]?.id || '';
		form = next;
		editingJobId = '';
	};

	const submitJob = async () => {
		if (!form.name.trim() || !form.target_knowledge_id || !form.extractor.model_id.trim()) {
			toast.error($i18n.t('Name, knowledge base, and extractor model are required.'));
			return;
		}

		savingJob = true;
		try {
			if (editingJobId) {
				await updateAutoKnowledgeJob(localStorage.token, editingJobId, form);
				toast.success($i18n.t('Job updated.'));
			} else {
				await createAutoKnowledgeJob(localStorage.token, form);
				toast.success($i18n.t('Auto Knowledge job created.'));
			}

			resetForm();
			await load();
			if (selectedJobId) await loadRuns(selectedJobId);
		} catch (error) {
			toast.error(`${error}`);
		} finally {
			savingJob = false;
		}
	};

	const editJob = (job: AutoKnowledgeJob) => {
		editingJobId = job.id;
		form = buildJobFormState(job, knowledgeBases[0]?.id || '');
	};

	const runJob = async (jobId: string) => {
		try {
			await runAutoKnowledgeJob(localStorage.token, jobId);
			toast.success($i18n.t('Auto Knowledge job queued.'));
			await load();
			await loadRuns(jobId);
		} catch (error) {
			toast.error(`${error}`);
		}
	};

	const toggleJob = async (job: AutoKnowledgeJob) => {
		try {
			await updateAutoKnowledgeJob(localStorage.token, job.id, {
				name: job.name,
				description: job.description,
				target_knowledge_id: job.target_knowledge_id,
				source_filter: job.source_filter,
				schedule: job.schedule,
				extractor: job.extractor,
				review_policy: job.review_policy,
				is_active: !job.is_active
			});
			toast.success($i18n.t('Job updated.'));
			await load();
			if (selectedJobId) await loadRuns(selectedJobId);
		} catch (error) {
			toast.error(`${error}`);
		}
	};

	const deleteJob = async (job: AutoKnowledgeJob) => {
		if (!confirm($i18n.t('Delete this Auto Knowledge job?'))) return;

		try {
			await deleteAutoKnowledgeJob(localStorage.token, job.id);
			toast.success($i18n.t('Job deleted.'));
			if (selectedJobId === job.id) {
				selectedJobId = '';
				runs = [];
			}
			if (editingJobId === job.id) resetForm();
			await load();
		} catch (error) {
			toast.error(`${error}`);
		}
	};

	const selectCandidate = async (candidate: AutoKnowledgeCandidate) => {
		try {
			const detail = await getAutoKnowledgeCandidate(localStorage.token, candidate.id);
			selectedCandidate = detail;
			reviewDraft = buildReviewDraft(detail);
		} catch (error) {
			toast.error(`${error}`);
			selectedCandidate = null;
			reviewDraft = null;
		}
	};

	const buildReviewPayload = () => {
		if (!reviewDraft) return {};

		return {
			question: reviewDraft.question,
			answer: reviewDraft.answer,
			category: reviewDraft.category,
			tags: parseTagsText(reviewDraft.tagsText),
			rejection_reason: reviewDraft.rejectionReason.trim() || undefined
		};
	};

	const reviewCandidate = async (action: 'approve' | 'approvePublish' | 'reject' | 'publish') => {
		if (!selectedCandidate) return;

		savingCandidate = true;
		try {
			if (action === 'approve') {
				await approveAutoKnowledgeCandidate(
					localStorage.token,
					selectedCandidate.id,
					buildReviewPayload(),
					false
				);
				toast.success($i18n.t('Candidate approved.'));
			} else if (action === 'approvePublish') {
				await approveAutoKnowledgeCandidate(
					localStorage.token,
					selectedCandidate.id,
					buildReviewPayload(),
					true
				);
				toast.success($i18n.t('Candidate published.'));
			} else if (action === 'reject') {
				await rejectAutoKnowledgeCandidate(
					localStorage.token,
					selectedCandidate.id,
					buildReviewPayload()
				);
				toast.success($i18n.t('Candidate rejected.'));
			} else {
				await publishAutoKnowledgeCandidate(localStorage.token, selectedCandidate.id);
				toast.success($i18n.t('Candidate published.'));
			}

			await load();
			if (selectedJobId) await loadRuns(selectedJobId);
		} catch (error) {
			toast.error(`${error}`);
		} finally {
			savingCandidate = false;
		}
	};

	onMount(async () => {
		await load();
	});
</script>

<div class="w-full px-4 pb-8">
	<div class="mx-auto flex max-w-7xl flex-col gap-4">
		<div class="flex flex-col gap-1 py-2">
			<div class="text-xl font-semibold text-gray-900 dark:text-gray-100">
				{$i18n.t('Auto Knowledge')}
			</div>
			<div class="text-sm text-gray-500 dark:text-gray-400">
				{$i18n.t('Operational chats into reviewed company knowledge.')}
			</div>
		</div>

		<div class="grid grid-cols-1 gap-4 xl:grid-cols-[360px_minmax(0,1fr)]">
			<div class="space-y-4">
				<TaskEditor
					bind:form
					{groups}
					{knowledgeBases}
					saving={savingJob}
					editing={Boolean(editingJobId)}
					on:submit={submitJob}
					on:cancelEdit={resetForm}
				/>

				<TaskList
					{jobs}
					{groups}
					{loading}
					{selectedJobId}
					on:refresh={load}
					on:select={(event) => loadRuns(event.detail.jobId)}
					on:run={(event) => runJob(event.detail.jobId)}
					on:toggle={(event) => toggleJob(event.detail.job)}
					on:edit={(event) => editJob(event.detail.job)}
					on:delete={(event) => deleteJob(event.detail.job)}
				/>
			</div>

			<div class="space-y-4">
				<RunHistory {runs} selectedJobName={selectedJob?.name ?? ''} />
				<CandidateList
					candidates={filteredCandidates}
					{jobs}
					{selectedCandidateId}
					filters={candidateFilters}
					on:select={(event) => selectCandidate(event.detail.candidate)}
				/>
			</div>
		</div>
	</div>

	<CandidateReviewDrawer
		open={Boolean(selectedCandidate && reviewDraft)}
		candidate={selectedCandidate}
		draft={reviewDraft}
		saving={savingCandidate}
		on:close={() => {
			selectedCandidate = null;
			reviewDraft = null;
		}}
		on:approve={() => reviewCandidate('approve')}
		on:approvePublish={() => reviewCandidate('approvePublish')}
		on:reject={() => reviewCandidate('reject')}
		on:publish={() => reviewCandidate('publish')}
	/>
</div>

import type {
	AutoKnowledgeGroup,
	AutoKnowledgeCandidateDetail,
	AutoKnowledgeJob,
	AutoKnowledgeJobFormState
} from './types';

export type CandidateRecord = {
	id: string;
	job_id: string;
	question: string;
	answer: string;
	category?: string | null;
	tags?: string[] | null;
	status: string;
	risk_level: string;
	meta?: Record<string, unknown> | null;
	published_file_id?: string | null;
};

export type CandidateFilters = {
	jobId?: string;
	status?: string;
	riskLevel?: string;
	query?: string;
};

export type ReviewDraft = {
	question: string;
	answer: string;
	category: string;
	tagsText: string;
	rejectionReason: string;
};

export type SourcePreviewItem = {
	id: string;
	title: string;
	body: string;
	meta: string;
};

export type CandidateAction = 'approve' | 'approve_publish' | 'reject' | 'publish';

export type RunSummaryInput = {
	status: string;
	input_count: number;
	generated_count: number;
	published_count: number;
	error?: string | null;
};

export const filterCandidates = <T extends CandidateRecord>(
	candidates: T[],
	filters: CandidateFilters
): T[] => {
	const query = (filters.query ?? '').trim().toLowerCase();

	return candidates.filter((candidate) => {
		if (filters.jobId && candidate.job_id !== filters.jobId) return false;
		if (filters.status && candidate.status !== filters.status) return false;
		if (filters.riskLevel && candidate.risk_level !== filters.riskLevel) return false;
		if (!query) return true;

		const haystack = [
			candidate.question,
			candidate.answer,
			candidate.category ?? '',
			(candidate.tags ?? []).join(' ')
		]
			.join(' ')
			.toLowerCase();

		return haystack.includes(query);
	});
};

export const buildReviewDraft = (candidate: Partial<CandidateRecord>): ReviewDraft => ({
	question: candidate.question ?? '',
	answer: candidate.answer ?? '',
	category: candidate.category ?? '',
	tagsText: (candidate.tags ?? []).join(', '),
	rejectionReason: ''
});

export const buildJobFormState = (
	job: Partial<AutoKnowledgeJob>,
	fallbackKnowledgeId = ''
): AutoKnowledgeJobFormState => ({
	name: job.name ?? '',
	description: job.description ?? '',
	target_knowledge_id: job.target_knowledge_id ?? fallbackKnowledgeId,
	source_filter: {
		lookback_hours: job.source_filter?.lookback_hours ?? 24,
		limit: job.source_filter?.limit ?? 1000,
		group_ids: job.source_filter?.group_ids ?? []
	},
	schedule: {
		rrule: job.schedule?.rrule ?? '',
		timezone: job.schedule?.timezone ?? Intl.DateTimeFormat().resolvedOptions().timeZone
	},
	extractor: {
		model_id: job.extractor?.model_id ?? ''
	},
	review_policy: {
		mode: job.review_policy?.mode ?? 'manual'
	},
	is_active: job.is_active ?? true
});

export const formatRunTimestamp = (timestampNs: number | null | undefined): string => {
	if (!timestampNs) return '-';
	return new Date(timestampNs / 1_000_000).toLocaleString();
};

export const formatDuration = (
	startedAtNs: number | null | undefined,
	finishedAtNs: number | null | undefined
): string => {
	if (startedAtNs == null || finishedAtNs == null || finishedAtNs <= startedAtNs) return '-';

	const totalSeconds = Math.floor((finishedAtNs - startedAtNs) / 1_000_000_000);
	const minutes = Math.floor(totalSeconds / 60);
	const seconds = totalSeconds % 60;

	if (minutes === 0) return `${seconds}s`;
	return `${minutes}m ${seconds}s`;
};

export const parseTagsText = (tagsText: string): string[] =>
	tagsText
		.split(',')
		.map((tag) => tag.trim())
		.filter(Boolean);

export const getSourceSummary = (candidate: {
	meta?: Record<string, unknown> | null;
	published_file_id?: string | null;
}): string[] => {
	const meta = candidate.meta ?? {};
	const sourceRoles = Array.isArray(meta.source_roles)
		? meta.source_roles.filter((role): role is string => typeof role === 'string')
		: [];
	const modelId = typeof meta.model_id === 'string' ? meta.model_id : '';
	const summary: string[] = [];

	if (sourceRoles.length > 0) {
		summary.push(`${sourceRoles.length} messages`);
		summary.push(sourceRoles.join('/'));
	}

	if (modelId) {
		summary.push(modelId);
	}

	if (candidate.published_file_id) {
		summary.push(`file:${candidate.published_file_id}`);
	}

	return summary;
};

export const getSourcePreviewItems = (
	candidate: Pick<AutoKnowledgeCandidateDetail, 'sources'>
): SourcePreviewItem[] =>
	(candidate.sources ?? []).map((source) => ({
		id: source.id,
		title: source.role || 'source',
		body: source.content?.trim() || source.message_id,
		meta: [source.chat_id, source.model_id].filter(Boolean).join(' · ')
	}));

export const getAvailableCandidateActions = (candidate: { status: string }): CandidateAction[] => {
	if (candidate.status === 'approved') {
		return ['publish'];
	}

	if (candidate.status === 'pending_review' || candidate.status === 'publish_failed') {
		return ['approve', 'approve_publish', 'reject'];
	}

	return [];
};

export const getRunSummary = (run: RunSummaryInput): string => {
	if (run.error) return run.error;
	if (run.input_count === 0 && run.generated_count === 0) {
		return 'No eligible chats found in this window.';
	}
	if (run.generated_count > 0 && run.published_count === 0) {
		return 'Candidates generated and awaiting review.';
	}
	if (run.published_count > 0) {
		return `${run.published_count} knowledge item(s) published.`;
	}
	return run.status;
};

export const buildGroupMap = (groups: AutoKnowledgeGroup[]): Record<string, string> =>
	Object.fromEntries(groups.map((group) => [group.id, group.name]));

export const getSourceScopeLabel = (
	job: Pick<AutoKnowledgeJob, 'source_filter'>,
	groupsById: Record<string, string>
): string => {
	const groupIds = job.source_filter?.group_ids ?? [];
	if (groupIds.length === 0) return 'All eligible chats';
	return groupIds.map((groupId) => groupsById[groupId] ?? groupId).join(', ');
};

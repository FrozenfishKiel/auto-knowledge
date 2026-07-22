import { describe, expect, it } from 'vitest';

import {
	buildGroupMap,
	buildJobFormState,
	buildReviewDraft,
	filterCandidates,
	formatDuration,
	formatRunTimestamp,
	getAvailableCandidateActions,
	getRunSummary,
	getSourcePreviewItems,
	getSourceSummary,
	getSourceScopeLabel
} from './utils';

describe('filterCandidates', () => {
	const candidates = [
		{
			id: 'c-1',
			job_id: 'job-1',
			question: 'How do refunds work?',
			answer: 'Refunds are allowed within 7 days.',
			category: 'After-sales',
			tags: ['refund', 'policy'],
			status: 'pending_review',
			risk_level: 'low'
		},
		{
			id: 'c-2',
			job_id: 'job-2',
			question: 'How do invoices work?',
			answer: 'Invoices are generated at month end.',
			category: 'Billing',
			tags: ['invoice'],
			status: 'approved',
			risk_level: 'medium'
		}
	];

	it('filters by job, status, risk, and search text together', () => {
		const result = filterCandidates(candidates, {
			jobId: 'job-1',
			status: 'pending_review',
			riskLevel: 'low',
			query: 'refund'
		});

		expect(result).toHaveLength(1);
		expect(result[0].id).toBe('c-1');
	});

	it('returns all candidates when filters are empty', () => {
		expect(filterCandidates(candidates, {})).toHaveLength(2);
	});
});

describe('buildReviewDraft', () => {
	it('copies editable candidate fields into a draft object', () => {
		const draft = buildReviewDraft({
			question: 'Q',
			answer: 'A',
			category: 'Ops',
			tags: ['one', 'two']
		});

		expect(draft).toEqual({
			question: 'Q',
			answer: 'A',
			category: 'Ops',
			tagsText: 'one, two',
			rejectionReason: ''
		});
	});
});

describe('buildJobFormState', () => {
	it('keeps source_filter.group_ids when entering edit mode', () => {
		const form = buildJobFormState(
			{
				name: 'Weekly Support',
				description: 'desc',
				target_knowledge_id: 'kb-1',
				source_filter: {
					lookback_hours: 168,
					limit: 2000,
					group_ids: ['support', 'ops']
				},
				schedule: {
					rrule: 'RRULE:FREQ=WEEKLY;BYDAY=MO',
					timezone: 'Asia/Shanghai'
				},
				extractor: {
					model_id: 'gpt-4o-mini'
				},
				review_policy: {
					mode: 'manual'
				},
				is_active: true
			},
			'kb-fallback'
		);

		expect(form.source_filter.group_ids).toEqual(['support', 'ops']);
		expect(form.target_knowledge_id).toBe('kb-1');
	});
});

describe('formatDuration', () => {
	it('formats finished runs as compact durations', () => {
		expect(formatDuration(0, 65_000_000_000)).toBe('1m 5s');
	});

	it('returns a dash for unfinished runs', () => {
		expect(formatDuration(0, null)).toBe('-');
	});
});

describe('formatRunTimestamp', () => {
	it('returns a fallback label when timestamp is missing', () => {
		expect(formatRunTimestamp(null)).toBe('-');
	});
});

describe('getSourceSummary', () => {
	it('derives source chips from candidate metadata', () => {
		const summary = getSourceSummary({
			meta: {
				model_id: 'gpt-4o-mini',
				source_roles: ['user', 'assistant']
			},
			published_file_id: 'file-1'
		});

		expect(summary).toEqual(['2 messages', 'user/assistant', 'gpt-4o-mini', 'file:file-1']);
	});
});

describe('getSourcePreviewItems', () => {
	it('builds readable source preview rows from candidate detail sources', () => {
		const items = getSourcePreviewItems({
			sources: [
				{
					id: 's-1',
					candidate_id: 'c-1',
					chat_id: 'chat-1',
					message_id: 'm-1',
					user_id: 'u-1',
					role: 'user',
					created_at: 1,
					content: 'Customer asked about refunds',
					model_id: null
				},
				{
					id: 's-2',
					candidate_id: 'c-1',
					chat_id: 'chat-1',
					message_id: 'm-2',
					user_id: 'u-1',
					role: 'assistant',
					created_at: 2,
					content: 'Refunds are allowed within 7 days',
					model_id: 'gpt-4o-mini'
				}
			]
		});

		expect(items).toEqual([
			{
				id: 's-1',
				title: 'user',
				body: 'Customer asked about refunds',
				meta: 'chat-1'
			},
			{
				id: 's-2',
				title: 'assistant',
				body: 'Refunds are allowed within 7 days',
				meta: 'chat-1 · gpt-4o-mini'
			}
		]);
	});
});

describe('getAvailableCandidateActions', () => {
	it('returns full review actions for pending candidates', () => {
		expect(getAvailableCandidateActions({ status: 'pending_review' })).toEqual([
			'approve',
			'approve_publish',
			'reject'
		]);
	});

	it('returns publish action for approved candidates only', () => {
		expect(getAvailableCandidateActions({ status: 'approved' })).toEqual(['publish']);
	});

	it('returns retry review actions for publish_failed candidates', () => {
		expect(getAvailableCandidateActions({ status: 'publish_failed' })).toEqual([
			'approve',
			'approve_publish',
			'reject'
		]);
	});
});

describe('getRunSummary', () => {
	it('reports a normal empty-window run clearly', () => {
		expect(
			getRunSummary({
				status: 'success',
				input_count: 0,
				generated_count: 0,
				published_count: 0,
				error: null
			})
		).toBe('No eligible chats found in this window.');
	});

	it('prefers explicit failure messages', () => {
		expect(
			getRunSummary({
				status: 'failed',
				input_count: 10,
				generated_count: 0,
				published_count: 0,
				error: 'Extractor output is not valid JSON'
			})
		).toBe('Extractor output is not valid JSON');
	});
});

describe('group scope helpers', () => {
	it('renders selected source groups as a human-readable scope', () => {
		const groupsById = buildGroupMap([
			{ id: 'support', name: 'Support' },
			{ id: 'ops', name: 'Operations' }
		]);

		expect(
			getSourceScopeLabel({ source_filter: { group_ids: ['support', 'ops'] } }, groupsById)
		).toBe('Support, Operations');
	});

	it('falls back when no source groups are configured', () => {
		expect(getSourceScopeLabel({ source_filter: {} }, {})).toBe('All eligible chats');
	});
});

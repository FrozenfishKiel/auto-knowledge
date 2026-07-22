export type AutoKnowledgeGroup = {
	id: string;
	name: string;
	member_count?: number;
};

export type AutoKnowledgeKnowledgeBase = {
	id: string;
	name: string;
};

export type AutoKnowledgeJob = {
	id: string;
	name: string;
	description?: string | null;
	target_knowledge_id: string;
	source_filter: {
		lookback_hours?: number;
		limit?: number;
		group_ids?: string[];
		user_ids?: string[];
		model_ids?: string[];
	};
	schedule: {
		rrule?: string;
		timezone?: string;
	};
	extractor: {
		model_id?: string;
	};
	review_policy: {
		mode?: string;
	};
	is_active: boolean;
	is_running: boolean;
	last_run_at?: number | null;
	next_run_at?: number | null;
};

export type AutoKnowledgeRun = {
	id: string;
	job_id: string;
	status: string;
	started_at: number;
	finished_at?: number | null;
	duration_ns?: number | null;
	duration_ms?: number | null;
	input_count: number;
	cleaned_count: number;
	generated_count: number;
	duplicate_count: number;
	failed_count: number;
	published_count: number;
	error?: string | null;
};

export type AutoKnowledgeCandidate = {
	id: string;
	job_id: string;
	run_id: string;
	target_knowledge_id: string;
	question: string;
	answer: string;
	category?: string | null;
	tags?: string[] | null;
	confidence: number;
	risk_level: string;
	status: string;
	duplicate_of?: string | null;
	rejection_reason?: string | null;
	published_file_id?: string | null;
	reviewed_by?: string | null;
	reviewed_at?: number | null;
	meta?: Record<string, unknown> | null;
	created_at: number;
	updated_at: number;
};

export type AutoKnowledgeSourcePreview = {
	id: string;
	candidate_id: string;
	chat_id: string;
	message_id: string;
	user_id: string;
	role: string;
	created_at: number;
	content?: string | null;
	model_id?: string | null;
};

export type AutoKnowledgeCandidateDetail = AutoKnowledgeCandidate & {
	sources: AutoKnowledgeSourcePreview[];
};

export type AutoKnowledgeJobFormState = {
	name: string;
	description: string;
	target_knowledge_id: string;
	source_filter: {
		lookback_hours: number;
		limit: number;
		group_ids: string[];
	};
	schedule: {
		rrule: string;
		timezone: string;
	};
	extractor: {
		model_id: string;
	};
	review_policy: {
		mode: string;
	};
	is_active: boolean;
};

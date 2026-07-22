import { WEBUI_API_BASE_URL } from '$lib/constants';

const request = async (token: string, path: string, options: RequestInit = {}) => {
	let error = null;
	const res = await fetch(`${WEBUI_API_BASE_URL}/auto-knowledge${path}`, {
		...options,
		headers: {
			Accept: 'application/json',
			'Content-Type': 'application/json',
			authorization: `Bearer ${token}`,
			...(options.headers ?? {})
		}
	})
		.then(async (res) => {
			if (!res.ok) throw await res.json();
			return res.json();
		})
		.catch((err) => {
			error = err.detail ?? err;
			console.error(err);
			return null;
		});

	if (error) throw error;
	return res;
};

export const getAutoKnowledgeJobs = async (token: string, status: string | null = null) => {
	const params = new URLSearchParams();
	if (status) params.set('status', status);
	return request(token, `/?${params.toString()}`);
};

export const createAutoKnowledgeJob = async (token: string, payload: object) => {
	return request(token, '/create', {
		method: 'POST',
		body: JSON.stringify(payload)
	});
};

export const updateAutoKnowledgeJob = async (token: string, id: string, payload: object) => {
	return request(token, `/${id}/update`, {
		method: 'POST',
		body: JSON.stringify(payload)
	});
};

export const deleteAutoKnowledgeJob = async (token: string, id: string) => {
	return request(token, `/${id}/delete`, { method: 'DELETE' });
};

export const runAutoKnowledgeJob = async (token: string, id: string) => {
	return request(token, `/${id}/run`, { method: 'POST' });
};

export const getAutoKnowledgeRuns = async (token: string, id: string) => {
	return request(token, `/${id}/runs`);
};

export const getAutoKnowledgeCandidates = async (
	token: string,
	jobId: string | null = null,
	status: string | null = null
) => {
	const params = new URLSearchParams();
	if (jobId) params.set('job_id', jobId);
	if (status) params.set('status', status);
	return request(token, `/candidates/list?${params.toString()}`);
};

export const getAutoKnowledgeCandidate = async (token: string, id: string) => {
	return request(token, `/candidates/${id}`);
};

export const approveAutoKnowledgeCandidate = async (
	token: string,
	id: string,
	payload: object = {},
	publish = false
) => {
	return request(token, `/candidates/${id}/approve?publish=${publish}`, {
		method: 'POST',
		body: JSON.stringify(payload)
	});
};

export const rejectAutoKnowledgeCandidate = async (token: string, id: string, payload: object = {}) => {
	return request(token, `/candidates/${id}/reject`, {
		method: 'POST',
		body: JSON.stringify(payload)
	});
};

export const publishAutoKnowledgeCandidate = async (token: string, id: string) => {
	return request(token, `/candidates/${id}/publish`, { method: 'POST' });
};

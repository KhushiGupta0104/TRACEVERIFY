// Thin client for the TRACEVERIFY FastAPI backend. All data shown in the UI comes from here.
// Empty in development (Vite proxies /api); the deployed API's URL in production builds.
const BASE = (import.meta.env.VITE_API_BASE_URL ?? '').replace(/\/+$/, '');

export class ApiError extends Error {
  constructor(message, status) {
    super(message);
    this.status = status;
  }
}

function describeDetail(detail) {
  if (!detail) return null;
  if (typeof detail === 'string') return detail;
  if (Array.isArray(detail)) {
    return detail.map((d) => `${(d.loc ?? []).slice(1).join('.') || 'request'}: ${d.msg}`).join('; ');
  }
  return JSON.stringify(detail);
}

async function request(path, options = {}) {
  let res;
  try {
    res = await fetch(`${BASE}${path}`, {
      headers: { 'Content-Type': 'application/json' },
      ...options,
    });
  } catch {
    throw new ApiError(
      BASE
        ? 'Cannot reach the TRACEVERIFY API. A sleeping free-tier server can take up to a minute to wake — please try again.'
        : 'Cannot reach the TRACEVERIFY API. Is the backend running on port 8000?',
      0,
    );
  }
  const body = await res.json().catch(() => null);
  if (!res.ok) {
    throw new ApiError(describeDetail(body?.detail) ?? `Request failed (${res.status})`, res.status);
  }
  return body;
}

export const api = {
  health: () => request('/api/health'),
  dataset: () => request('/api/dataset'),
  rules: () => request('/api/rules'),
  seeds: () => request('/api/investigations/seeds'),
  recent: () => request('/api/investigations'),
  start: (payload) => request('/api/investigations/start', { method: 'POST', body: JSON.stringify(payload) }),
  rerun: (id, payload) => request(`/api/investigations/${id}/rerun`, { method: 'POST', body: JSON.stringify(payload) }),
  investigation: (id) => request(`/api/investigations/${id}`),
  timeline: (id, includeRejected = false) =>
    request(`/api/investigations/${id}/events?include_rejected=${includeRejected}`),
  relationships: (id, status = 'accepted') => request(`/api/investigations/${id}/relationships?status=${status}`),
  event: (id) => request(`/api/events/${id}`),
};

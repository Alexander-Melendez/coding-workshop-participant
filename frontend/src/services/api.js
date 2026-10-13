/**
 * HTTP client for the project-tracker API.
 *
 * - Adds the bearer token to every request.
 * - On a 401, refreshes the access token once and retries the request.
 * - Turns every failure (HTTP or network) into an ApiError with a
 *   user-readable message and optional per-field errors.
 */
import { buildQuery } from '../lib/routes.js';

const SERVICE_PATH = '/api/project-tracker';
const TOKEN_KEY = 'acme.tokens';

/** Error thrown for any failed API call. */
export class ApiError extends Error {
  constructor(status, code, message, fields = {}) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.code = code;
    this.fields = fields;
  }
}

function envBaseUrl() {
  try {
    return (import.meta.env?.VITE_API_URL || '').replace(/\/$/, '');
  } catch {
    return '';
  }
}

const settings = {
  baseUrl: `${envBaseUrl()}${SERVICE_PATH}`,
  fetchImpl: (...args) => globalThis.fetch(...args),
  storage: typeof window !== 'undefined' ? window.localStorage : null,
  onAuthLost: () => {},
};

/** Override settings (used by tests and by the auth provider). */
export function configureApi(overrides) {
  Object.assign(settings, overrides);
}

// ---- token storage (localStorage can throw in private mode, so guard it) ----
export function getTokens() {
  try {
    return JSON.parse(settings.storage?.getItem(TOKEN_KEY) || 'null');
  } catch {
    return null;
  }
}

export function setTokens(tokens) {
  try {
    settings.storage?.setItem(TOKEN_KEY, JSON.stringify({
      access: tokens.access_token,
      refresh: tokens.refresh_token,
    }));
  } catch {
    /* storage unavailable: session lasts until reload */
  }
}

export function clearTokens() {
  try {
    settings.storage?.removeItem(TOKEN_KEY);
  } catch {
    /* ignore */
  }
}

let refreshInFlight = null;

async function refreshTokens() {
  const tokens = getTokens();
  if (!tokens?.refresh) return false;
  if (!refreshInFlight) {
    refreshInFlight = (async () => {
      try {
        const data = await request('POST', '/auth/refresh', {
          body: { refresh_token: tokens.refresh }, auth: false,
        });
        setTokens(data);
        return true;
      } catch {
        return false;
      } finally {
        refreshInFlight = null;
      }
    })();
  }
  return refreshInFlight;
}

/**
 * Make an API request.
 * @param {string} method HTTP method
 * @param {string} path path below the service, e.g. "/projects"
 * @param {{body?: object, query?: object, auth?: boolean, retry?: boolean}} options
 * @returns {Promise<any>} parsed JSON body (null for 204)
 */
export async function request(method, path, {
  body, query, auth = true, retry = true,
} = {}) {
  const headers = { Accept: 'application/json' };
  if (body !== undefined) headers['Content-Type'] = 'application/json';
  const tokens = auth ? getTokens() : null;
  if (tokens?.access) {
    headers.Authorization = `Bearer ${tokens.access}`;
    // Fallback header in case a proxy strips Authorization
    headers['X-Auth-Token'] = tokens.access;
  }

  let response;
  try {
    response = await settings.fetchImpl(`${settings.baseUrl}${path}${buildQuery(query)}`, {
      method,
      headers,
      body: body !== undefined ? JSON.stringify(body) : undefined,
    });
  } catch {
    throw new ApiError(0, 'network_error', "Can't reach the server. Check your connection and try again.");
  }

  if (response.status === 401 && auth && retry && tokens?.refresh) {
    if (await refreshTokens()) return request(method, path, { body, query, auth, retry: false });
  }

  const text = await response.text();
  let data = null;
  if (text) {
    try {
      data = JSON.parse(text);
    } catch {
      data = null;
    }
  }

  if (!response.ok) {
    const error = data?.error || {};
    if (response.status === 401 && auth) {
      clearTokens();
      settings.onAuthLost(error.message);
    }
    throw new ApiError(
      response.status,
      error.code || 'http_error',
      error.message || `Request failed (${response.status})`,
      error.fields || {},
    );
  }
  return data;
}

export const api = {
  get: (path, query) => request('GET', path, { query }),
  post: (path, body = {}) => request('POST', path, { body }),
  put: (path, body = {}) => request('PUT', path, { body }),
  del: (path) => request('DELETE', path),
};

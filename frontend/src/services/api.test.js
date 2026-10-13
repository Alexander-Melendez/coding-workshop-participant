/**
 * API client tests with a mocked fetch: auth headers, error shape,
 * network failures and automatic token refresh.
 */
import { beforeEach, test } from 'node:test';
import assert from 'node:assert/strict';
import {
  ApiError, api, configureApi, getTokens, request, setTokens,
} from './api.js';

function memoryStorage() {
  const data = new Map();
  return {
    getItem: (k) => (data.has(k) ? data.get(k) : null),
    setItem: (k, v) => data.set(k, String(v)),
    removeItem: (k) => data.delete(k),
  };
}

function reply(status, body) {
  return { status, ok: status >= 200 && status < 300, text: async () => (body === undefined ? '' : JSON.stringify(body)) };
}

let calls;
let lost;

function mockFetch(responses) {
  calls = [];
  configureApi({
    fetchImpl: async (url, init) => {
      calls.push({ url, init });
      const next = responses.shift();
      if (next instanceof Error) throw next;
      return next;
    },
  });
}

beforeEach(() => {
  lost = null;
  configureApi({ baseUrl: 'https://api.test/api/project-tracker', storage: memoryStorage(), onAuthLost: (m) => { lost = m; } });
});

test('sends bearer token and parses JSON', async () => {
  setTokens({ access_token: 'A1', refresh_token: 'R1' });
  mockFetch([reply(200, [{ id: 1 }])]);
  const data = await api.get('/projects', { search: 'srv', status: '' });
  assert.deepEqual(data, [{ id: 1 }]);
  assert.equal(calls[0].url, 'https://api.test/api/project-tracker/projects?search=srv');
  assert.equal(calls[0].init.headers.Authorization, 'Bearer A1');
});

test('204 returns null', async () => {
  mockFetch([reply(204)]);
  assert.equal(await api.del('/users/3'), null);
});

test('API errors keep code, message and field errors', async () => {
  mockFetch([reply(400, { error: { code: 'validation_error', message: 'Fix fields', fields: { name: 'Required' } } })]);
  await assert.rejects(api.post('/projects', {}), (err) => {
    assert.ok(err instanceof ApiError);
    assert.equal(err.status, 400);
    assert.equal(err.code, 'validation_error');
    assert.deepEqual(err.fields, { name: 'Required' });
    return true;
  });
});

test('network failure becomes a friendly ApiError', async () => {
  mockFetch([new TypeError('Failed to fetch')]);
  await assert.rejects(api.get('/projects'), (err) => err.code === 'network_error' && err.status === 0);
});

test('expired access token is refreshed once and the request retried', async () => {
  setTokens({ access_token: 'old', refresh_token: 'R1' });
  mockFetch([
    reply(401, { error: { code: 'unauthorized', message: 'expired' } }),
    reply(200, { access_token: 'new', refresh_token: 'R2' }),
    reply(200, { ok: true }),
  ]);
  assert.deepEqual(await api.get('/auth/me'), { ok: true });
  assert.equal(calls[1].url.endsWith('/auth/refresh'), true);
  assert.equal(calls[2].init.headers.Authorization, 'Bearer new');
  assert.equal(getTokens().refresh, 'R2');
});

test('failed refresh signs the user out', async () => {
  setTokens({ access_token: 'old', refresh_token: 'R1' });
  mockFetch([
    reply(401, { error: { code: 'unauthorized', message: 'expired' } }),
    reply(401, { error: { code: 'unauthorized', message: 'refresh expired' } }),
    reply(401, { error: { code: 'unauthorized', message: 'Your session has expired.' } }),
  ]);
  await assert.rejects(api.get('/auth/me'), (err) => err.status === 401);
  assert.equal(getTokens(), null);
  assert.ok(lost);
});

test('login failures do not trigger sign-out handling', async () => {
  mockFetch([reply(401, { error: { code: 'unauthorized', message: 'Invalid username or password' } })]);
  await assert.rejects(request('POST', '/auth/login', { body: {}, auth: false }), /Invalid username/);
  assert.equal(lost, null);
});

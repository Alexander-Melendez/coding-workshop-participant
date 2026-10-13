/**
 * Unit tests for pure helpers. Run with: npm test (Node's built-in test runner).
 */
import { test } from 'node:test';
import assert from 'node:assert/strict';
import {
  clampPct, describeDeadline, daysUntil, formatDate, formatHours, formatMoney, formatRange,
  healthLabel, parseDate, toISODate,
} from './format.js';
import { buildQuery, matchRoute, resolveRoute } from './routes.js';
import {
  dateOrder, email, first, hoursInDay, minLength, nonNegative, required, username,
} from './validators.js';

test('formatMoney rounds to whole dollars and handles missing values', () => {
  assert.equal(formatMoney(12500.4), '$12,500');
  assert.equal(formatMoney(50, { cents: true }), '$50.00');
  assert.equal(formatMoney(null), '—');
});

test('formatHours drops trailing zeros', () => {
  assert.equal(formatHours(8), '8 h');
  assert.equal(formatHours(7.5), '7.5 h');
  assert.equal(formatHours(undefined), '—');
});

test('dates are parsed as local days (no UTC shift)', () => {
  const d = parseDate('2026-01-02');
  assert.equal(d.getDate(), 2);
  assert.equal(toISODate(d), '2026-01-02');
  assert.equal(formatDate('2026-10-13'), 'Oct 13, 2026');
  assert.equal(formatRange('2026-10-01', '2026-12-20'), 'Oct 1 – Dec 20, 2026');
  assert.equal(formatRange('2025-12-01', '2026-01-20'), 'Dec 1, 2025 – Jan 20, 2026');
  assert.equal(parseDate('nope'), null);
});

test('deadlines read naturally', () => {
  const today = new Date(2026, 9, 13);
  assert.equal(daysUntil('2026-10-20', today), 7);
  assert.equal(describeDeadline('2026-10-13', today), 'Due today');
  assert.equal(describeDeadline('2026-10-14', today), 'Due tomorrow');
  assert.equal(describeDeadline('2026-10-23', today), '10 days left');
  assert.equal(describeDeadline('2026-10-10', today), '3 days overdue');
});

test('health labels follow the white/red/green rule', () => {
  assert.equal(healthLabel('white'), 'In progress');
  assert.equal(healthLabel('red'), 'Over budget');
  assert.equal(healthLabel('green'), 'Completed');
  assert.equal(healthLabel('white', true), 'Archived');
  assert.equal(clampPct(150), 100);
  assert.equal(clampPct(Number.NaN), 0);
});

test('route matching', () => {
  assert.deepEqual(matchRoute('/projects/:id', '/projects/12'), { id: '12' });
  assert.deepEqual(matchRoute('/projects', '/projects/'), {});
  assert.equal(matchRoute('/projects/:id', '/projects'), null);
  assert.equal(matchRoute('/', '/people'), null);
  const routes = [{ path: '/' }, { path: '/projects/:id' }];
  assert.equal(resolveRoute(routes, '/projects/3').route.path, '/projects/:id');
  assert.equal(resolveRoute(routes, '/nope'), null);
});

test('buildQuery skips empty values', () => {
  assert.equal(buildQuery({ search: 'srv', status: '', at_risk: false, page: 0 }), '?search=srv&page=0');
  assert.equal(buildQuery({}), '');
});

test('validators mirror the API rules', () => {
  assert.ok(required('  '));
  assert.equal(required('x'), '');
  assert.ok(email('not-an-email'));
  assert.equal(email('a@b.io'), '');
  assert.ok(username('a b'));
  assert.equal(username('maria.m'), '');
  assert.ok(nonNegative('-1'));
  assert.equal(nonNegative('0'), '');
  assert.ok(minLength(8)('short'));
  assert.ok(dateOrder('2026-02-01', '2026-01-01'));
  assert.equal(dateOrder('2026-01-01', '2026-01-01'), '');
  assert.ok(hoursInDay('9'));
  assert.ok(hoursInDay('0'));
  assert.ok(hoursInDay('7.3'));
  assert.equal(hoursInDay('7.75'), '');
  assert.equal(first('', 'second', 'third'), 'second');
});

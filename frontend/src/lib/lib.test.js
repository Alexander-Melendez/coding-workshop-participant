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
import { layoutMilestones, milestoneState } from './graph.js';
import {
  dateOrder, email, first, hoursInDay, minLength, nonNegative, readyAfter, required,
  startsAfterPredecessors,
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

test('milestones start after the milestones they depend on', () => {
  const open = { title: 'Plan', end_date: '2026-10-31', completed_at: null };
  const doneEarly = { title: 'Survey', end_date: '2026-10-31', completed_at: '2026-10-10T15:04:00' };
  assert.equal(readyAfter(open), '2026-10-31');
  assert.equal(readyAfter(doneEarly), '2026-10-10');
  assert.match(startsAfterPredecessors('2026-10-31', [open]), /after Plan ends/);
  assert.equal(startsAfterPredecessors('2026-11-01', [open]), '');
  assert.equal(startsAfterPredecessors('2026-10-11', [doneEarly]), '');
  assert.equal(startsAfterPredecessors('2026-10-01', []), '');
});

// --- milestone dependency graph -------------------------------------------
const ms = (id, extra = {}) => ({
  id, title: `M${id}`, status: 'not_started', overdue: false, start_date: `2026-01-0${id}`, end_date: '2026-12-31', depends_on: [], waiting_on: [], ...extra,
});

test('graph: a chain becomes one straight path, one column per step', () => {
  const layout = layoutMilestones([
    ms(1, { status: 'complete' }),
    ms(2, { status: 'in_progress', depends_on: [{ id: 1, complete: true }] }),
    ms(3, { depends_on: [{ id: 2, complete: false }], waiting_on: ['M2'] }),
  ]);
  assert.deepEqual(layout.nodes.map((n) => [n.id, n.col, n.row, n.state]), [
    [1, 0, 0, 'complete'], [2, 1, 0, 'in_progress'], [3, 2, 0, 'waiting'],
  ]);
  assert.equal(layout.columns, 3);
  assert.equal(layout.rows, 1);
  assert.deepEqual(layout.edges, [{ from: 1, to: 2, done: true }, { from: 2, to: 3, done: false }]);
});

test('graph: a milestone waiting on two others sits right of the deepest one', () => {
  const layout = layoutMilestones([
    ms(1), ms(2), ms(3, { depends_on: [{ id: 1 }] }),
    ms(4, { depends_on: [{ id: 2 }, { id: 3 }], waiting_on: ['M2', 'M3'] }),
  ]);
  const pos = Object.fromEntries(layout.nodes.map((n) => [n.id, [n.col, n.row]]));
  assert.deepEqual(pos, { 1: [0, 0], 2: [0, 1], 3: [1, 0], 4: [2, 0] });
  assert.equal(layout.rows, 2);
});

test('graph: milestones one after another line up even without a dependency', () => {
  const layout = layoutMilestones([
    ms(2, { start_date: '2026-03-01', end_date: '2026-04-30' }),
    ms(1, { start_date: '2026-01-01', end_date: '2026-02-28' }),
  ]);
  assert.deepEqual(layout.nodes.map((n) => [n.id, n.col, n.row]), [[1, 0, 0], [2, 1, 0]]);
  assert.deepEqual(layout.edges, []); // no dependency, so no line
});

test('graph: overdue outranks waiting; complete outranks everything', () => {
  assert.equal(milestoneState(ms(1, { overdue: true, waiting_on: ['X'] })), 'overdue');
  assert.equal(milestoneState(ms(1, { status: 'complete', overdue: true })), 'complete');
  assert.equal(milestoneState(ms(1, { status: 'in_progress' })), 'in_progress');
});

test('graph: bad data with a loop does not hang', () => {
  const layout = layoutMilestones([ms(1, { depends_on: [{ id: 2 }] }), ms(2, { depends_on: [{ id: 1 }] })]);
  assert.equal(layout.nodes.length, 2);
});

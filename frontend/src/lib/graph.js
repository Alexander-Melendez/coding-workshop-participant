/**
 * Milestone dependency graph: pure layout logic, unit tested.
 *
 * Milestones are placed left to right in the order they happen: after their
 * predecessors and after anything that finished before they start. Ones that
 * run at the same time stack in a column. A chain becomes a straight path;
 * a milestone waiting on two others shows as a fork joining.
 */

export const STATE_LABELS = {
  complete: 'Complete',
  overdue: 'Overdue',
  waiting: 'Waiting',
  in_progress: 'In progress',
  not_started: 'Not started',
};

/**
 * One visual state per milestone, most important first:
 * complete > overdue > waiting on a predecessor > in progress / not started.
 */
export function milestoneState(m) {
  if (m.status === 'complete') return 'complete';
  if (m.overdue) return 'overdue';
  if (m.waiting_on?.length) return 'waiting';
  return m.status;
}

/**
 * @param {Array} milestones from the API (id, title, status, overdue, start_date, end_date, depends_on, waiting_on)
 * @returns {{ nodes: Array, edges: Array, columns: number, rows: number }}
 */
export function layoutMilestones(milestones) {
  const byId = new Map(milestones.map((m) => [m.id, m]));
  const byStart = (a, b) => (a.start_date < b.start_date ? -1 : a.start_date > b.start_date ? 1 : a.id - b.id);
  const ordered = [...milestones].sort(byStart);
  const endOf = (m) => m.end_date || m.start_date;
  const col = new Map();

  // A milestone goes one column right of everything it depends on, and of
  // everything that finished before it started. Only milestones that run
  // at the same time share a column.
  const colOf = (m, visiting = new Set()) => {
    if (col.has(m.id)) return col.get(m.id);
    if (visiting.has(m.id)) return 0; // the API rejects loops; this just keeps bad data from hanging the page
    visiting.add(m.id);
    const after = [
      ...(m.depends_on || []).map((d) => byId.get(d.id)).filter(Boolean),
      ...ordered.filter((o) => o.id !== m.id && endOf(o) < m.start_date),
    ];
    const c = after.length ? 1 + Math.max(...after.map((o) => colOf(o, visiting))) : 0;
    col.set(m.id, c);
    return c;
  };
  ordered.forEach((m) => colOf(m));

  const columns = [];
  ordered.forEach((m) => (columns[col.get(m.id)] ||= []).push(m));

  const nodes = [];
  columns.forEach((list = [], c) => {
    list.forEach((m, row) => {
      const state = milestoneState(m);
      nodes.push({ id: m.id, title: m.title, col: c, row, state, label: STATE_LABELS[state] || '' });
    });
  });

  const edges = [];
  milestones.forEach((m) => {
    (m.depends_on || []).forEach((d) => {
      if (byId.has(d.id)) edges.push({ from: d.id, to: m.id, done: Boolean(d.complete) });
    });
  });

  return {
    nodes,
    edges,
    columns: columns.length,
    rows: Math.max(0, ...columns.map((c) => (c ? c.length : 0))),
  };
}

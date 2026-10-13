/**
 * Display formatting helpers. Pure functions, unit tested in format.test.js.
 */

const money = new Intl.NumberFormat('en-US', {
  style: 'currency',
  currency: 'USD',
  maximumFractionDigits: 0,
});
const moneyCents = new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD' });
const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
const DAY_MS = 86400000;

/** Format a number as whole dollars, e.g. $12,500. */
export function formatMoney(value, { cents = false } = {}) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return '—';
  return (cents ? moneyCents : money).format(Number(value));
}

/** Format hours, dropping trailing zeros: 8 -> "8 h", 7.5 -> "7.5 h". */
export function formatHours(value) {
  if (value === null || value === undefined) return '—';
  const n = Math.round(Number(value) * 100) / 100;
  return `${n.toLocaleString('en-US')} h`;
}

/** Parse YYYY-MM-DD as a local date (avoids the UTC off-by-one of new Date('2026-01-02')). */
export function parseDate(iso) {
  if (!iso) return null;
  const [y, m, d] = String(iso).slice(0, 10).split('-').map(Number);
  if (!y || !m || !d) return null;
  return new Date(y, m - 1, d);
}

/** Local date as YYYY-MM-DD. */
export function toISODate(date) {
  const y = date.getFullYear();
  const m = String(date.getMonth() + 1).padStart(2, '0');
  const d = String(date.getDate()).padStart(2, '0');
  return `${y}-${m}-${d}`;
}

/** Today's local date as YYYY-MM-DD. */
export function todayISO() {
  return toISODate(new Date());
}

/** "Oct 13, 2026" (or "Oct 13" when withYear is false). */
export function formatDate(iso, { withYear = true } = {}) {
  const date = parseDate(iso);
  if (!date) return '—';
  const base = `${MONTHS[date.getMonth()]} ${date.getDate()}`;
  return withYear ? `${base}, ${date.getFullYear()}` : base;
}

/** "Oct 1 – Dec 20, 2026" style range. */
export function formatRange(startIso, endIso) {
  const start = parseDate(startIso);
  const end = parseDate(endIso);
  if (!start || !end) return '—';
  const sameYear = start.getFullYear() === end.getFullYear();
  return `${formatDate(startIso, { withYear: !sameYear })} – ${formatDate(endIso)}`;
}

/** Date and time for audit entries, in the viewer's locale. */
export function formatDateTime(iso) {
  if (!iso) return '—';
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return '—';
  return date.toLocaleString('en-US', {
    month: 'short', day: 'numeric', year: 'numeric', hour: 'numeric', minute: '2-digit',
  });
}

/** Whole days from today to the given date (negative = in the past). */
export function daysUntil(iso, today = new Date()) {
  const date = parseDate(iso);
  if (!date) return null;
  const start = new Date(today.getFullYear(), today.getMonth(), today.getDate());
  return Math.round((date - start) / DAY_MS);
}

/** Human description of a deadline: "Due today", "12 days left", "3 days overdue". */
export function describeDeadline(iso, today = new Date()) {
  const days = daysUntil(iso, today);
  if (days === null) return '';
  if (days === 0) return 'Due today';
  if (days === 1) return 'Due tomorrow';
  if (days > 1) return `${days} days left`;
  if (days === -1) return '1 day overdue';
  return `${-days} days overdue`;
}

/** First name for greetings. */
export function firstName(name) {
  return String(name || '').trim().split(/\s+/)[0] || '';
}

const HEALTH_LABELS = { white: 'In progress', red: 'Over budget', green: 'Completed' };
const STATUS_LABELS = { not_started: 'Not started', in_progress: 'In progress', complete: 'Complete' };
const ROLE_LABELS = { admin: 'Admin', manager: 'Manager', employee: 'Employee' };

/** Label for a project health colour. */
export function healthLabel(health, archived = false) {
  if (archived) return 'Archived';
  return HEALTH_LABELS[health] || health;
}

/** Label for a milestone status. */
export function statusLabel(status) {
  return STATUS_LABELS[status] || status;
}

/** Label for a role. */
export function roleLabel(role) {
  return ROLE_LABELS[role] || role;
}

/** Clamp a percentage to 0-100. */
export function clampPct(value) {
  if (!Number.isFinite(value)) return 0;
  return Math.max(0, Math.min(100, value));
}

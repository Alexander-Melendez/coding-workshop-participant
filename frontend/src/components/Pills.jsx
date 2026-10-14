import PropTypes from 'prop-types';
import { healthLabel, roleLabel, statusLabel } from '../lib/format.js';

/** White / red / green project status. */
export function HealthPill({ health, archived }) {
  const tone = archived ? 'green' : health;
  return <span className={`pill pill--${tone}`}>{healthLabel(health, archived)}</span>;
}

HealthPill.propTypes = { health: PropTypes.oneOf(['white', 'red', 'green']).isRequired, archived: PropTypes.bool };

const MILESTONE_TONES = { not_started: 'white', in_progress: 'blue', complete: 'green' };

/** Milestone status: red when overdue, slate while waiting on another milestone. */
export function MilestonePill({ status, overdue, waiting }) {
  if (status !== 'complete' && overdue) return <span className="pill pill--red">Overdue</span>;
  if (status !== 'complete' && waiting) return <span className="pill pill--slate">Waiting</span>;
  return <span className={`pill pill--${MILESTONE_TONES[status]}`}>{statusLabel(status)}</span>;
}

MilestonePill.propTypes = { status: PropTypes.string.isRequired, overdue: PropTypes.bool, waiting: PropTypes.bool };

/** Role badge. */
export function RolePill({ role }) {
  const tone = { admin: 'amber', manager: 'blue', employee: 'white' }[role];
  return <span className={`pill pill--plain pill--${tone}`}>{roleLabel(role)}</span>;
}

RolePill.propTypes = { role: PropTypes.string.isRequired };

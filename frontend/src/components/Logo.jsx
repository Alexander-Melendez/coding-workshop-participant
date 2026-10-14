import PropTypes from 'prop-types';

/**
 * Hexpath PT mark: a hexagon (work that fits together with no gaps or overlaps)
 * around a Gantt-style timeline: two completed milestones (solid diamonds)
 * and one still to go (hollow).
 * The accent is light blue for dark backgrounds; set --logo-accent
 * (e.g. #2f6fb3) to use it on white.
 */
export default function Logo({ size = 22 }) {
  const accent = 'var(--logo-accent, #8ec5f5)';
  return (
    <svg className="logo" width={size} height={size} viewBox="0 0 24 24" aria-hidden="true" focusable="false">
      <path d="M12 1.5 21.1 6.75v10.5L12 22.5 2.9 17.25V6.75z" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinejoin="round" />
      <path d="M6 12h9.6" fill="none" stroke={accent} strokeWidth="1.2" strokeLinecap="round" />
      <path d="M6.5 10.1 8.4 12 6.5 13.9 4.6 12z" fill={accent} />
      <path d="M12 10.1 13.9 12 12 13.9 10.1 12z" fill={accent} />
      <path d="M17.5 10.1 19.4 12 17.5 13.9 15.6 12z" fill="none" stroke={accent} strokeWidth="1.1" strokeLinejoin="round" />
    </svg>
  );
}

Logo.propTypes = { size: PropTypes.number };

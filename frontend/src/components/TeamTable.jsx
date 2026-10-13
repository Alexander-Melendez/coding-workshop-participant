import PropTypes from 'prop-types';
import { Link } from '../lib/router.jsx';
import { formatDate, formatHours } from '../lib/format.js';
import { ProgressBar } from './BudgetGauge.jsx';

/**
 * Who is working on what, and how many of this week's 40 hours they've logged.
 * Employees work on one milestone at a time, so "Unassigned" means available.
 */
export default function TeamTable({ team, showManager }) {
  return (
    <div className="table-wrap">
      <table className="table">
        <thead>
          <tr>
            <th scope="col">Person</th>
            {showManager && <th scope="col">Manager</th>}
            <th scope="col">Working on</th>
            <th scope="col">This week</th>
          </tr>
        </thead>
        <tbody>
          {team.map((member) => (
            <tr key={member.id}>
              <td>
                <span className="cell-title">{member.name}</span>
                <span className="cell-sub">{`${member.display_id}${member.title ? `, ${member.title}` : ''}`}</span>
              </td>
              {showManager && <td>{member.manager_name || <span className="faint">None</span>}</td>}
              <td>
                {member.current_assignment ? (
                  <>
                    <Link to={`/projects/${member.current_assignment.project_id}`}>
                      {member.current_assignment.milestone_title}
                    </Link>
                    <span className="cell-sub">
                      {`${member.current_assignment.project_title}, until ${formatDate(member.current_assignment.end_date, { withYear: false })}`}
                    </span>
                  </>
                ) : (
                  <span className="pill pill--amber">Unassigned</span>
                )}
              </td>
              <td style={{ minWidth: 140 }}>
                <span className="num">{`${formatHours(member.hours_this_week)} of 40`}</span>
                <ProgressBar
                  value={member.utilization_pct}
                  tone="ink"
                  label={`${member.name}: ${member.utilization_pct}% of 40 hours logged this week`}
                />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

TeamTable.propTypes = {
  team: PropTypes.arrayOf(PropTypes.shape({
    id: PropTypes.number.isRequired,
    name: PropTypes.string.isRequired,
    display_id: PropTypes.string,
    title: PropTypes.string,
    manager_name: PropTypes.string,
    hours_this_week: PropTypes.number,
    utilization_pct: PropTypes.number,
    current_assignment: PropTypes.shape({
      project_id: PropTypes.number,
      project_title: PropTypes.string,
      milestone_title: PropTypes.string,
      end_date: PropTypes.string,
    }),
  })).isRequired,
  showManager: PropTypes.bool,
};

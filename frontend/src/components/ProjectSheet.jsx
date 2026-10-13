import PropTypes from 'prop-types';
import { Link } from '../lib/router.jsx';
import { describeDeadline, formatHours, formatRange } from '../lib/format.js';
import BudgetGauge, { ProgressBar } from './BudgetGauge.jsx';
import { HealthPill } from './Pills.jsx';

/**
 * A project as a coloured sheet: white = in progress, red = over budget,
 * green = completed or archived (completed_at / archived_at set).
 */
export default function ProjectSheet({ project }) {
  const showCosts = project.budget !== undefined;
  const archived = Boolean(project.archived_at);

  return (
    <article className={`sheet sheet--${project.health}`} data-testid="project-sheet">
      <div className="sheet-head">
        <div>
          <h3><Link to={`/projects/${project.id}`}>{project.title}</Link></h3>
          <p className="sheet-meta">{`Managed by ${project.manager.name}`}</p>
        </div>
        <HealthPill health={project.health} archived={archived} />
      </div>

      {project.at_risk && (
        <div className="risk">
          <span aria-hidden="true">▲</span>
          <span>
            <strong>At risk: </strong>
            {project.risk_reasons.join('; ')}
          </span>
        </div>
      )}

      {showCosts && (
        <BudgetGauge budget={Number(project.budget)} spent={project.spent} forecast={project.forecast} />
      )}

      <ProgressBar
        value={project.progress_pct}
        label={`${project.milestones_completed} of ${project.milestones_total} milestones complete`}
      />

      <dl className="sheet-stats">
        <div>
          <dt>Milestones</dt>
          <dd>{`${project.milestones_completed} of ${project.milestones_total} done`}</dd>
        </div>
        <div>
          <dt>Hours logged</dt>
          <dd>{formatHours(project.hours_logged)}</dd>
        </div>
        <div>
          <dt>Timeline</dt>
          <dd>{formatRange(project.start_date, project.end_date)}</dd>
        </div>
        <div>
          <dt>Deadline</dt>
          <dd>{project.completed_at ? 'Delivered' : describeDeadline(project.end_date)}</dd>
        </div>
      </dl>
    </article>
  );
}

export const projectShape = PropTypes.shape({
  id: PropTypes.number.isRequired,
  title: PropTypes.string.isRequired,
  health: PropTypes.oneOf(['white', 'red', 'green']).isRequired,
  manager: PropTypes.shape({ id: PropTypes.number, name: PropTypes.string }).isRequired,
  completed_at: PropTypes.string,
  archived_at: PropTypes.string,
  at_risk: PropTypes.bool,
  risk_reasons: PropTypes.arrayOf(PropTypes.string),
  budget: PropTypes.oneOfType([PropTypes.number, PropTypes.string]),
  spent: PropTypes.number,
  forecast: PropTypes.number,
  progress_pct: PropTypes.number,
  milestones_completed: PropTypes.number,
  milestones_total: PropTypes.number,
  hours_logged: PropTypes.number,
  start_date: PropTypes.string,
  end_date: PropTypes.string,
});

ProjectSheet.propTypes = { project: projectShape.isRequired };

/** Grid of project sheets. */
export function ProjectSheets({ projects }) {
  return (
    <div className="sheets">
      {projects.map((p) => <ProjectSheet key={p.id} project={p} />)}
    </div>
  );
}

ProjectSheets.propTypes = { projects: PropTypes.arrayOf(projectShape).isRequired };

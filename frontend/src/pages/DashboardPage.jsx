import PropTypes from 'prop-types';
import { PageHead } from '../components/Layout.jsx';
import { ProjectSheets } from '../components/ProjectSheet.jsx';
import TeamTable from '../components/TeamTable.jsx';
import LogTimeForm from '../components/LogTimeForm.jsx';
import { ProgressBar } from '../components/BudgetGauge.jsx';
import { EmptyState, ErrorState, Loading } from '../components/States.jsx';
import { useToast } from '../components/Toasts.jsx';
import { Link } from '../lib/router.jsx';
import { useApi } from '../lib/hooks.js';
import {
  describeDeadline, firstName, formatDate, formatDateTime, formatHours, formatRange, todayISO,
} from '../lib/format.js';
import { useAuth } from '../services/auth.jsx';
import { getDashboard, listAssignments } from '../services/tracker.js';

/** Home page; content depends on the signed-in role. */
export default function DashboardPage() {
  const { user } = useAuth();
  const { data, error, loading, reload } = useApi(getDashboard, []);

  if (error) return <div className="page"><ErrorState error={error} onRetry={reload} /></div>;
  if (loading && !data) return <Loading label="Loading your overview…" />;
  if (data.role === 'employee') return <EmployeeDashboard data={data} user={user} onChange={reload} />;
  return <StaffDashboard data={data} user={user} />;
}

// ---------------------------------------------------------------------------
function StaffDashboard({ data, user }) {
  const { summary } = data;
  const atRisk = data.projects.filter((p) => p.at_risk);
  const isAdmin = data.role === 'admin';

  return (
    <div className="page">
      <PageHead
        title={`Hello, ${firstName(user.name)}`}
        description={isAdmin
          ? 'Every active project, who is working on what, and what changed recently.'
          : 'Your projects, your team, and the milestones coming up.'}
        actions={isAdmin && <Link className="button button--primary" to="/projects?new=1">New project</Link>}
      />

      <dl className="strip">
        <div className="figure"><dt>Active projects</dt><dd>{summary.active_projects}</dd></div>
        <div className={`figure ${summary.at_risk_projects ? 'figure--amber' : ''}`}>
          <dt>At risk</dt><dd>{summary.at_risk_projects}</dd>
        </div>
        <div className={`figure ${summary.over_budget_projects ? 'figure--red' : ''}`}>
          <dt>Over budget</dt><dd>{summary.over_budget_projects}</dd>
        </div>
        <div className="figure">
          <dt>Available people</dt>
          <dd>
            {summary.unassigned_employees}
            <small>{` of ${summary.team_size}`}</small>
          </dd>
        </div>
      </dl>

      {atRisk.length > 0 && (
        <section className="panel" aria-labelledby="attention">
          <div className="panel-head"><h2 id="attention">Needs attention</h2></div>
          <ul className="activity">
            {atRisk.map((p) => (
              <li key={p.id}>
                <Link to={`/projects/${p.id}`}><strong>{p.title}</strong></Link>
                <span className="muted">{`: ${p.risk_reasons.join('; ')}`}</span>
              </li>
            ))}
          </ul>
        </section>
      )}

      <section aria-labelledby="projects-heading" className="stack">
        <div className="panel-head" style={{ marginBottom: 0 }}>
          <h2 id="projects-heading">{isAdmin ? 'Projects' : 'Your projects'}</h2>
          <Link to="/projects">See all projects</Link>
        </div>
        {data.projects.length ? <ProjectSheets projects={data.projects} /> : (
          <EmptyState title="No active projects">
            {isAdmin ? 'Create a project and assign a manager to get started.' : 'An admin will add you to a project.'}
          </EmptyState>
        )}
      </section>

      <div className="split">
        <section className="panel" aria-labelledby="team-heading">
          <div className="panel-head">
            <h2 id="team-heading">{isAdmin ? 'Who is working on what' : 'Your team'}</h2>
            <Link to="/people">{isAdmin ? 'Manage people' : 'Manage team'}</Link>
          </div>
          {data.team.length ? <TeamTable team={data.team} showManager={isAdmin} /> : (
            <EmptyState title="No employees yet">
              {isAdmin ? 'Add employees on the People page.' : 'An admin assigns employees to you.'}
            </EmptyState>
          )}
        </section>

        <div className="stack stack--loose">
          <section className="panel" aria-labelledby="due-heading">
            <div className="panel-head"><h2 id="due-heading">Due in the next 2 weeks</h2></div>
            {data.upcoming_milestones.length ? (
              <ul className="activity">
                {data.upcoming_milestones.map((m) => (
                  <li key={m.id}>
                    <Link to={`/projects/${m.project_id}`}>{m.title}</Link>
                    <span className="cell-sub">{m.project_title}</span>
                    <span className={m.overdue ? 'pill pill--red' : 'pill pill--white'}>{describeDeadline(m.end_date)}</span>
                  </li>
                ))}
              </ul>
            ) : <p className="muted small">Nothing due soon.</p>}
          </section>

          {isAdmin && (
            <section className="panel" aria-labelledby="activity-heading">
              <div className="panel-head">
                <h2 id="activity-heading">Recent activity</h2>
                <Link to="/audit">Audit log</Link>
              </div>
              <ul className="activity">
                {data.recent_activity.map((a) => (
                  <li key={a.id}>
                    {a.summary}
                    <time dateTime={a.created_at}>{`${a.actor_name || 'System'}, ${formatDateTime(a.created_at)}`}</time>
                  </li>
                ))}
              </ul>
            </section>
          )}
        </div>
      </div>
    </div>
  );
}

StaffDashboard.propTypes = {
  data: PropTypes.shape({
    role: PropTypes.string,
    summary: PropTypes.object,
    projects: PropTypes.array,
    team: PropTypes.array,
    upcoming_milestones: PropTypes.array,
    recent_activity: PropTypes.array,
  }).isRequired,
  user: PropTypes.shape({ name: PropTypes.string }).isRequired,
};

// ---------------------------------------------------------------------------
const WEEKDAYS = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];

function EmployeeDashboard({ data, user, onChange }) {
  const toast = useToast();
  const { week } = data;
  const today = todayISO();
  const assignmentsApi = useApi(() => listAssignments(), []);
  const current = data.current_assignment;

  return (
    <div className="page">
      <PageHead
        title={`Hello, ${firstName(user.name)}`}
        description={current
          ? `You're on ${current.milestone_title} for ${current.project_title} until ${formatDate(current.end_date)}.`
          : "You're not assigned to a milestone right now."}
      />

      <div className="split">
        <section className="panel" aria-labelledby="week-heading">
          <div className="panel-head">
            <h2 id="week-heading">This week</h2>
            <p>{formatRange(week.start, week.end)}</p>
          </div>
          <div className="week" aria-label="Hours logged per day this week">
            {week.days.map((day, i) => (
              <div key={day.date} className={`day ${day.date === today ? 'day--today' : ''}`}>
                <div className="day-bar"><span style={{ height: `${(Number(day.hours) / 8) * 100}%` }} /></div>
                <strong>{Number(day.hours) ? Number(day.hours) : '–'}</strong>
                <span>{WEEKDAYS[i]}</span>
              </div>
            ))}
          </div>
          <div style={{ marginTop: 'var(--s4)' }}>
            <p className="num small" style={{ marginBottom: 6 }}>
              <strong>{formatHours(week.total_hours)}</strong>
              {` of ${week.target_hours} logged, ${formatHours(week.remaining_hours)} left`}
            </p>
            <ProgressBar value={(week.total_hours / week.target_hours) * 100} tone="ink" label="Hours logged this week" />
          </div>
        </section>

        <section className="panel" aria-labelledby="log-heading">
          <div className="panel-head">
            <h2 id="log-heading">{week.logged_today ? 'Logged today' : 'Log today'}</h2>
            <Link to="/time">All entries</Link>
          </div>
          {week.logged_today && <p className="muted small">You&apos;ve logged today. Edit it from your entries, or log another day below.</p>}
          {assignmentsApi.data && (
            <LogTimeForm
              assignments={assignmentsApi.data}
              onSaved={() => { toast('Hours logged'); onChange(); }}
            />
          )}
        </section>
      </div>

      {data.upcoming_assignments.length > 0 && (
        <section className="panel" aria-labelledby="next-heading">
          <div className="panel-head"><h2 id="next-heading">Coming up</h2></div>
          <ul className="activity">
            {data.upcoming_assignments.map((a) => (
              <li key={a.id}>
                <strong>{a.milestone_title}</strong>
                <span className="muted">{` on ${a.project_title}, ${formatRange(a.start_date, a.end_date)}`}</span>
              </li>
            ))}
          </ul>
        </section>
      )}

      <section aria-labelledby="my-projects" className="stack">
        <h2 id="my-projects">Your projects</h2>
        {data.projects.length ? <ProjectSheets projects={data.projects} /> : (
          <EmptyState title="No projects yet">Projects appear here once your manager assigns you to a milestone.</EmptyState>
        )}
      </section>
    </div>
  );
}

EmployeeDashboard.propTypes = {
  data: PropTypes.shape({
    current_assignment: PropTypes.object,
    upcoming_assignments: PropTypes.array,
    week: PropTypes.object,
    projects: PropTypes.array,
  }).isRequired,
  user: PropTypes.shape({ name: PropTypes.string }).isRequired,
  onChange: PropTypes.func.isRequired,
};

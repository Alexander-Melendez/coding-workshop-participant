import { useState } from 'react';
import PropTypes from 'prop-types';
import { PageHead } from '../components/Layout.jsx';
import BudgetGauge, { ProgressBar } from '../components/BudgetGauge.jsx';
import { HealthPill, MilestonePill } from '../components/Pills.jsx';
import ProjectFormModal, { ManagerSelect } from '../components/ProjectForm.jsx';
import { AssignModal, MilestoneFormModal } from '../components/MilestoneForms.jsx';
import Modal, { ConfirmDialog } from '../components/Modal.jsx';
import { EmptyState, ErrorState, Loading } from '../components/States.jsx';
import { useToast } from '../components/Toasts.jsx';
import { Link } from '../lib/router.jsx';
import { useApi } from '../lib/hooks.js';
import {
  describeDeadline, formatDate, formatDateTime, formatHours, formatMoney, formatRange,
} from '../lib/format.js';
import { useAuth } from '../services/auth.jsx';
import * as tracker from '../services/tracker.js';

/** One project: summary, milestones, assignments, team and budget history. */
export default function ProjectDetailPage({ params }) {
  const id = Number(params.id);
  const { user } = useAuth();
  const toast = useToast();
  const project = useApi(() => tracker.getProject(id), [id]);
  const milestones = useApi(() => tracker.listMilestones(id), [id]);
  const [modal, setModal] = useState(null); // { type, milestone? }
  const [confirm, setConfirm] = useState(null); // { title, message, label, danger, run, done }
  const [confirmState, setConfirmState] = useState({ busy: false, error: '' });

  const refresh = () => {
    project.reload();
    milestones.reload();
  };

  if (project.error) return <div className="page"><ErrorState error={project.error} onRetry={project.reload} /></div>;
  if (!project.data) return <Loading label="Loading project…" />;

  const p = project.data;
  const perms = p.permissions;
  const isAdmin = user.role === 'admin';

  const ask = (options) => {
    setConfirmState({ busy: false, error: '' });
    setConfirm(options);
  };
  const runConfirm = async () => {
    setConfirmState({ busy: true, error: '' });
    try {
      await confirm.run();
      toast(confirm.done);
      setConfirm(null);
      refresh();
    } catch (error) {
      setConfirmState({ busy: false, error: error.message });
    }
  };
  const closeModal = () => setModal(null);
  const saved = (message) => () => {
    setModal(null);
    toast(message);
    refresh();
  };

  return (
    <div className="page">
      <p className="small"><Link to="/projects">All projects</Link></p>
      <PageHead
        title={p.title}
        description={p.description}
        actions={(
          <>
            {perms.can_edit && <button type="button" className="button" onClick={() => setModal({ type: 'edit' })}>Edit project</button>}
            {perms.can_change_manager && <button type="button" className="button" onClick={() => setModal({ type: 'manager' })}>Change manager</button>}
            {perms.can_complete && (
              <button
                type="button"
                className="button button--primary"
                onClick={() => ask({
                  title: 'Complete this project?',
                  message: 'Every milestone is complete. The project becomes read-only and turns green. An admin can then archive it.',
                  label: 'Complete project',
                  done: 'Project completed',
                  run: () => tracker.completeProject(id),
                })}
              >
                Complete project
              </button>
            )}
            {perms.can_archive && (
              <button
                type="button"
                className="button button--danger"
                onClick={() => ask({
                  title: 'Archive this project?',
                  message: 'Archived projects are hidden from managers and employees. Admins can still view and restore them.',
                  label: 'Archive project',
                  danger: true,
                  done: 'Project archived',
                  run: () => tracker.archiveProject(id),
                })}
              >
                Archive
              </button>
            )}
            {perms.can_restore && (
              <button
                type="button"
                className="button"
                onClick={() => ask({
                  title: 'Restore this project?',
                  message: 'Its manager and team will see it again.',
                  label: 'Restore project',
                  done: 'Project restored',
                  run: () => tracker.restoreProject(id),
                })}
              >
                Restore
              </button>
            )}
          </>
        )}
      />

      <ProjectSummary project={p} />

      {!p.completed_at && !p.archived_at && p.milestones_total > 0 && p.milestones_completed < p.milestones_total && perms.can_edit && (
        <p className="faint small">
          {`Complete all ${p.milestones_total} milestones to complete the project (${p.milestones_completed} done).`}
        </p>
      )}

      <section className="panel" aria-labelledby="milestones-heading">
        <div className="panel-head">
          <div>
            <h2 id="milestones-heading">Milestones</h2>
            <p>Key deliverables, each with its own dates and team.</p>
          </div>
          {perms.can_manage_milestones && (
            <button type="button" className="button button--primary" onClick={() => setModal({ type: 'milestone' })}>Add milestone</button>
          )}
        </div>
        {milestones.error && <ErrorState error={milestones.error} onRetry={milestones.reload} />}
        {milestones.data && milestones.data.length === 0 && (
          <EmptyState title="No milestones yet">
            {perms.can_manage_milestones
              ? 'Break the project into milestones, for example the first 200 servers, then assign people to each.'
              : 'The project manager has not added milestones yet.'}
          </EmptyState>
        )}
        {milestones.data && milestones.data.length > 0 && (
          <div className="milestones">
            {milestones.data.map((m) => (
              <MilestoneRow
                key={m.id}
                milestone={m}
                canManage={perms.can_manage_milestones}
                showCost={perms.can_view_costs}
                onEdit={() => setModal({ type: 'milestone', milestone: m })}
                onAssign={() => setModal({ type: 'assign', milestone: m })}
                onComplete={() => ask({
                  title: `Complete ${m.title}?`,
                  message: 'Completed milestones are locked: dates, assignments and logged hours can no longer change. Assigned people are freed from tomorrow.',
                  label: 'Complete milestone',
                  done: `${m.title} completed`,
                  run: () => tracker.completeMilestone(m.id),
                })}
                onDelete={() => ask({
                  title: `Delete ${m.title}?`,
                  message: 'This removes the milestone and its assignments. Milestones with logged hours cannot be deleted.',
                  label: 'Delete milestone',
                  danger: true,
                  done: 'Milestone deleted',
                  run: () => tracker.deleteMilestone(m.id),
                })}
                onUnassign={(a) => ask({
                  title: `Remove ${a.employee_name} from ${m.title}?`,
                  message: 'Hours they already logged are kept.',
                  label: 'Remove',
                  danger: true,
                  done: `${a.employee_name} removed`,
                  run: () => tracker.deleteAssignment(a.id),
                })}
              />
            ))}
          </div>
        )}
      </section>

      {perms.can_view_costs && (
        <div className="split">
          <TeamPanel team={p.team || []} />
          <BudgetHistoryPanel projectId={id} key={`${p.budget}`} />
        </div>
      )}

      {modal?.type === 'edit' && <ProjectFormModal project={p} onClose={closeModal} onSaved={saved('Project saved')} />}
      {modal?.type === 'manager' && <ManagerModal project={p} onClose={closeModal} onSaved={saved('Manager changed')} />}
      {modal?.type === 'milestone' && (
        <MilestoneFormModal
          project={p}
          milestone={modal.milestone}
          onClose={closeModal}
          onSaved={saved(modal.milestone ? 'Milestone saved' : 'Milestone added')}
        />
      )}
      {modal?.type === 'assign' && (
        <AssignModal milestone={modal.milestone} isAdmin={isAdmin} onClose={closeModal} onSaved={saved('Employee assigned')} />
      )}
      {confirm && (
        <ConfirmDialog
          title={confirm.title}
          message={confirm.message}
          confirmLabel={confirm.label}
          danger={confirm.danger}
          busy={confirmState.busy}
          error={confirmState.error}
          onConfirm={runConfirm}
          onClose={() => setConfirm(null)}
        />
      )}
    </div>
  );
}

ProjectDetailPage.propTypes = { params: PropTypes.shape({ id: PropTypes.string }).isRequired };

// ---------------------------------------------------------------------------
function ProjectSummary({ project: p }) {
  const showCosts = p.budget !== undefined;
  const estimate = Number(p.estimated_hours);
  const hoursPct = estimate ? ((p.hours_logged / estimate) * 100) : 0;
  return (
    <section className={`sheet sheet--${p.health}`} aria-label="Project summary">
      <div className="sheet-head">
        <div>
          <p className="sheet-meta">
            {`${formatRange(p.start_date, p.end_date)}. `}
            {p.completed_at ? `Completed ${formatDateTime(p.completed_at)}.` : `${describeDeadline(p.end_date)}.`}
          </p>
          <p className="sheet-meta">{`Managed by ${p.manager.name}`}</p>
        </div>
        <HealthPill health={p.health} archived={Boolean(p.archived_at)} />
      </div>

      {p.at_risk && (
        <div className="risk">
          <span aria-hidden="true">▲</span>
          <span>
            <strong>At risk: </strong>
            {p.risk_reasons.join('; ')}
          </span>
        </div>
      )}

      {showCosts && (
        <BudgetGauge budget={Number(p.budget)} spent={p.spent} forecast={p.forecast} large />
      )}

      <dl className="figures">
        {showCosts && (
          <>
            <div className="figure"><dt>Budget</dt><dd>{formatMoney(p.budget)}</dd></div>
            <div className={`figure ${p.spent > Number(p.budget) ? 'figure--red' : ''}`}>
              <dt>Spent</dt>
              <dd>
                {formatMoney(p.spent)}
                <small>{` ${p.budget_used_pct}%`}</small>
              </dd>
            </div>
            <div className={`figure ${p.forecast > Number(p.budget) ? 'figure--amber' : ''}`}>
              <dt>Forecast at completion</dt>
              <dd>{formatMoney(p.forecast)}</dd>
            </div>
            <div className="figure"><dt>Remaining</dt><dd>{formatMoney(p.remaining)}</dd></div>
          </>
        )}
        <div className="figure">
          <dt>Hours logged</dt>
          <dd>
            {formatHours(p.hours_logged)}
            {estimate > 0 && <small>{` of ${formatHours(estimate)}`}</small>}
          </dd>
        </div>
        <div className="figure"><dt>Hours still assigned</dt><dd>{formatHours(p.hours_assigned)}</dd></div>
        <div className="figure">
          <dt>Milestones</dt>
          <dd>
            {p.milestones_completed}
            <small>{` of ${p.milestones_total} complete`}</small>
          </dd>
        </div>
      </dl>
      {estimate > 0 && (
        <ProgressBar value={hoursPct} tone={hoursPct > 100 ? 'over' : 'ink'} label="Hours logged against estimate" />
      )}
    </section>
  );
}

ProjectSummary.propTypes = { project: PropTypes.object.isRequired };

// ---------------------------------------------------------------------------
function MilestoneRow({
  milestone: m, canManage, showCost, onEdit, onAssign, onComplete, onDelete, onUnassign,
}) {
  const open = canManage && !m.locked;
  const markState = m.overdue ? 'overdue' : m.status;
  return (
    <article className="milestone" data-testid="milestone">
      <span className={`milestone-mark milestone-mark--${markState}`} aria-hidden="true" />
      <div className="milestone-body">
        <div className="actions">
          <h3>{m.title}</h3>
          <MilestonePill status={m.status} overdue={m.overdue} />
        </div>
        {m.description && <p className="muted small">{m.description}</p>}
        <p className="small num">
          {formatRange(m.start_date, m.end_date)}
          {`, ${formatHours(m.hours_logged)} logged`}
          {showCost && `, ${formatMoney(m.cost)}`}
          {m.locked && m.completed_at && `, completed ${formatDate(m.completed_at.slice(0, 10))}`}
        </p>
        {m.assignments.length > 0 ? (
          <ul className="chips" aria-label="Assigned people">
            {m.assignments.map((a) => (
              <li key={a.id} className={`chip ${open ? '' : 'chip--static'}`}>
                {`${a.employee_name}, ${formatRange(a.start_date, a.end_date)}`}
                {open && (
                  <button type="button" aria-label={`Remove ${a.employee_name}`} onClick={() => onUnassign(a)}>×</button>
                )}
              </li>
            ))}
          </ul>
        ) : (!m.locked && <p className="faint small">Nobody assigned yet.</p>)}
      </div>
      {open && (
        <div className="milestone-actions">
          <button type="button" className="button button--small" onClick={onAssign}>Assign</button>
          <button type="button" className="button button--small" onClick={onComplete}>Complete</button>
          <button type="button" className="button button--small" onClick={onEdit}>Edit</button>
          <button type="button" className="button button--small button--danger" onClick={onDelete}>Delete</button>
        </div>
      )}
    </article>
  );
}

MilestoneRow.propTypes = {
  milestone: PropTypes.object.isRequired,
  canManage: PropTypes.bool,
  showCost: PropTypes.bool,
  onEdit: PropTypes.func.isRequired,
  onAssign: PropTypes.func.isRequired,
  onComplete: PropTypes.func.isRequired,
  onDelete: PropTypes.func.isRequired,
  onUnassign: PropTypes.func.isRequired,
};

// ---------------------------------------------------------------------------
function TeamPanel({ team }) {
  return (
    <section className="panel" aria-labelledby="team-heading">
      <div className="panel-head">
        <div>
          <h2 id="team-heading">People and cost</h2>
          <p>Hours logged on this project. Cost is hours times salary divided by 2,080, shown for people whose salary you can see.</p>
        </div>
      </div>
      {team.length === 0 ? <p className="muted small">Nobody has been assigned yet.</p> : (
        <div className="table-wrap">
          <table className="table">
            <thead>
              <tr>
                <th scope="col">Person</th>
                <th scope="col" className="right">Hours</th>
                <th scope="col" className="right">Cost</th>
              </tr>
            </thead>
            <tbody>
              {team.map((member) => (
                <tr key={member.id} className={member.archived ? 'is-archived' : ''}>
                  <td>
                    <span className="cell-title">{member.name}</span>
                    <span className="cell-sub">{`${member.display_id}${member.archived ? ', archived' : ''}`}</span>
                  </td>
                  <td className="right num">{formatHours(member.hours)}</td>
                  <td className="right num">{formatMoney(member.cost)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}

TeamPanel.propTypes = { team: PropTypes.array.isRequired };

function BudgetHistoryPanel({ projectId }) {
  const history = useApi(() => tracker.getBudgetHistory(projectId), [projectId]);
  return (
    <section className="panel" aria-labelledby="budget-heading">
      <div className="panel-head"><h2 id="budget-heading">Budget history</h2></div>
      {history.error && <ErrorState error={history.error} onRetry={history.reload} />}
      {history.data && (
        <ul className="activity">
          {history.data.map((h) => (
            <li key={h.id}>
              <strong className="num">{formatMoney(h.new_budget)}</strong>
              {Number(h.old_budget) > 0 && (
                <span className="muted">
                  {` (${Number(h.change) > 0 ? '+' : ''}${formatMoney(h.change)})`}
                </span>
              )}
              {h.reason && <span>{` ${h.reason}`}</span>}
              <time dateTime={h.changed_at}>{`${h.changed_by_name}, ${formatDateTime(h.changed_at)}`}</time>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

BudgetHistoryPanel.propTypes = { projectId: PropTypes.number.isRequired };

function ManagerModal({ project, onClose, onSaved }) {
  const [managerId, setManagerId] = useState(String(project.manager.id));
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const save = async (event) => {
    event.preventDefault();
    if (!managerId) {
      setError('Choose a manager');
      return;
    }
    setBusy(true);
    try {
      await tracker.setProjectManager(project.id, Number(managerId));
      onSaved();
    } catch (err) {
      setError(err.message);
      setBusy(false);
    }
  };
  return (
    <Modal title="Change manager" description="Each project has one manager." onClose={onClose}>
      <form className="form" onSubmit={save} noValidate>
        <ManagerSelect name="manager_id" value={managerId} onChange={(e) => setManagerId(e.target.value)} error={error} />
        <div className="modal-foot">
          <button type="button" className="button" onClick={onClose}>Cancel</button>
          <button type="submit" className="button button--primary" disabled={busy}>{busy ? 'Saving…' : 'Save manager'}</button>
        </div>
      </form>
    </Modal>
  );
}

ManagerModal.propTypes = {
  project: PropTypes.shape({ id: PropTypes.number, manager: PropTypes.shape({ id: PropTypes.number }) }).isRequired,
  onClose: PropTypes.func.isRequired,
  onSaved: PropTypes.func.isRequired,
};

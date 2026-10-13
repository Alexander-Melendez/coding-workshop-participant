import { useState } from 'react';
import PropTypes from 'prop-types';
import { PageHead } from '../components/Layout.jsx';
import Field from '../components/Field.jsx';
import LogTimeForm from '../components/LogTimeForm.jsx';
import Modal, { ConfirmDialog } from '../components/Modal.jsx';
import { EmptyState, ErrorState, Loading } from '../components/States.jsx';
import { useToast } from '../components/Toasts.jsx';
import { Link } from '../lib/router.jsx';
import { useApi } from '../lib/hooks.js';
import { formatDate, formatHours, formatMoney } from '../lib/format.js';
import { useAuth } from '../services/auth.jsx';
import * as tracker from '../services/tracker.js';

/** Employees log and edit their hours; managers and admins review timesheets. */
export default function TimePage() {
  const { user } = useAuth();
  return user.role === 'employee' ? <EmployeeTime /> : <StaffTime isAdmin={user.role === 'admin'} />;
}

// ---------------------------------------------------------------------------
function EmployeeTime() {
  const toast = useToast();
  const assignments = useApi(() => tracker.listAssignments(), []);
  const entries = useApi(() => tracker.listTimeEntries(), []);
  const [editing, setEditing] = useState(null);
  const [deleting, setDeleting] = useState(null);
  const [deleteState, setDeleteState] = useState({ busy: false, error: '' });

  const remove = async () => {
    setDeleteState({ busy: true, error: '' });
    try {
      await tracker.deleteTimeEntry(deleting.id);
      setDeleting(null);
      toast('Entry deleted');
      entries.reload();
    } catch (error) {
      setDeleteState({ busy: false, error: error.message });
    }
  };

  return (
    <div className="page">
      <PageHead
        title="Log time"
        description="Log the hours you worked each day on the milestone you're assigned to: up to 8 a day and 40 a week."
      />
      <div className="split">
        <section className="panel" aria-labelledby="entries-heading">
          <div className="panel-head"><h2 id="entries-heading">Your entries</h2></div>
          {entries.error && <ErrorState error={entries.error} onRetry={entries.reload} />}
          {entries.loading && !entries.data && <Loading />}
          {entries.data?.length === 0 && <EmptyState title="No hours logged yet">Use the form to log your first day.</EmptyState>}
          {entries.data?.length > 0 && (
            <EntriesTable
              entries={entries.data}
              onEdit={setEditing}
              onDelete={(entry) => { setDeleteState({ busy: false, error: '' }); setDeleting(entry); }}
            />
          )}
        </section>
        <section className="panel" aria-labelledby="log-heading">
          <div className="panel-head"><h2 id="log-heading">Log hours</h2></div>
          {assignments.error && <ErrorState error={assignments.error} onRetry={assignments.reload} />}
          {assignments.data && (
            <LogTimeForm assignments={assignments.data} onSaved={() => { toast('Hours logged'); entries.reload(); }} />
          )}
        </section>
      </div>

      {editing && (
        <Modal title={`Edit ${formatDate(editing.work_date)}`} description={`${editing.milestone_title}, ${editing.project_title}`} onClose={() => setEditing(null)}>
          <LogTimeForm
            assignments={assignments.data || []}
            entry={editing}
            submitLabel="Save entry"
            onCancel={() => setEditing(null)}
            onSaved={() => { setEditing(null); toast('Entry saved'); entries.reload(); }}
          />
        </Modal>
      )}
      {deleting && (
        <ConfirmDialog
          title="Delete this entry?"
          message={`${formatHours(deleting.hours)} on ${formatDate(deleting.work_date)} for ${deleting.milestone_title}.`}
          confirmLabel="Delete entry"
          danger
          busy={deleteState.busy}
          error={deleteState.error}
          onConfirm={remove}
          onClose={() => setDeleting(null)}
        />
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
function StaffTime({ isAdmin }) {
  const [filters, setFilters] = useState({
    project_id: '', user_id: '', date_from: '', date_to: '',
  });
  const projects = useApi(() => tracker.listProjects(), []);
  const people = useApi(() => tracker.listUsers(isAdmin ? { role: 'employee' } : {}), [isAdmin]);
  const entries = useApi(() => tracker.listTimeEntries(filters), [filters]);
  const set = (name) => (e) => setFilters((prev) => ({ ...prev, [name]: e.target.value }));

  const totalHours = (entries.data || []).reduce((sum, e) => sum + Number(e.hours), 0);
  const totalCost = (entries.data || []).reduce((sum, e) => sum + Number(e.cost || 0), 0);

  return (
    <div className="page">
      <PageHead
        title="Timesheets"
        description={isAdmin ? 'Hours logged across every project.' : 'Hours logged on your projects and by your team.'}
      />
      <div className="toolbar">
        <Field label="Project" name="project_id" as="select" value={filters.project_id} onChange={set('project_id')}>
          <option value="">All projects</option>
          {(projects.data || []).map((p) => <option key={p.id} value={p.id}>{p.title}</option>)}
        </Field>
        <Field label="Person" name="user_id" as="select" value={filters.user_id} onChange={set('user_id')}>
          <option value="">Everyone</option>
          {(people.data || []).map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
        </Field>
        <Field label="From" name="date_from" type="date" value={filters.date_from} onChange={set('date_from')} />
        <Field label="To" name="date_to" type="date" value={filters.date_to} onChange={set('date_to')} />
      </div>

      {entries.data && (
        <dl className="strip">
          <div className="figure"><dt>Entries</dt><dd>{entries.data.length}</dd></div>
          <div className="figure"><dt>Hours</dt><dd>{formatHours(totalHours)}</dd></div>
          <div className="figure">
            <dt>{isAdmin ? 'Cost' : 'Cost of your team'}</dt>
            <dd>{formatMoney(totalCost)}</dd>
          </div>
        </dl>
      )}
      {entries.error && <ErrorState error={entries.error} onRetry={entries.reload} />}
      {entries.loading && !entries.data && <Loading />}
      {entries.data?.length === 0 && <EmptyState title="No hours match these filters" />}
      {entries.data?.length > 0 && <EntriesTable entries={entries.data} showPerson />}
    </div>
  );
}

StaffTime.propTypes = { isAdmin: PropTypes.bool };

// ---------------------------------------------------------------------------
function EntriesTable({
  entries, showPerson, onEdit, onDelete,
}) {
  const showCost = entries.some((e) => e.cost !== undefined);
  return (
    <div className="table-wrap">
      <table className="table">
        <thead>
          <tr>
            <th scope="col">Date</th>
            {showPerson && <th scope="col">Person</th>}
            <th scope="col">Milestone</th>
            <th scope="col" className="right">Hours</th>
            {showCost && <th scope="col" className="right">Cost</th>}
            {onEdit && <th scope="col"><span className="visually-hidden">Actions</span></th>}
          </tr>
        </thead>
        <tbody>
          {entries.map((e) => (
            <tr key={e.id}>
              <td className="nowrap">{formatDate(e.work_date)}</td>
              {showPerson && <td>{e.employee_name}</td>}
              <td>
                <Link to={`/projects/${e.project_id}`}>{e.milestone_title}</Link>
                <span className="cell-sub">{e.project_title}</span>
                {e.note && <span className="cell-sub">{e.note}</span>}
              </td>
              <td className="right num">{formatHours(e.hours)}</td>
              {showCost && <td className="right num">{e.cost !== undefined ? formatMoney(e.cost, { cents: true }) : ''}</td>}
              {onEdit && (
                <td>
                  {e.locked ? <span className="faint small">Locked</span> : (
                    <div className="actions" style={{ flexWrap: 'nowrap', justifyContent: 'flex-end' }}>
                      <button type="button" className="button button--small" onClick={() => onEdit(e)}>Edit</button>
                      <button type="button" className="button button--small button--danger" onClick={() => onDelete(e)}>Delete</button>
                    </div>
                  )}
                </td>
              )}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

EntriesTable.propTypes = {
  entries: PropTypes.arrayOf(PropTypes.object).isRequired,
  showPerson: PropTypes.bool,
  onEdit: PropTypes.func,
  onDelete: PropTypes.func,
};

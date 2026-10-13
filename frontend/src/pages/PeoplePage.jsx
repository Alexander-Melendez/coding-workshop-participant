import { useState } from 'react';
import { PageHead } from '../components/Layout.jsx';
import Field from '../components/Field.jsx';
import Modal, { ConfirmDialog } from '../components/Modal.jsx';
import { RolePill } from '../components/Pills.jsx';
import UserFormModal, { TemporaryPassword } from '../components/UserForms.jsx';
import { EmptyState, ErrorState, Loading } from '../components/States.jsx';
import { useToast } from '../components/Toasts.jsx';
import { Link } from '../lib/router.jsx';
import { useApi, useDebounced } from '../lib/hooks.js';
import { formatDate, formatHours, formatMoney } from '../lib/format.js';
import { useAuth } from '../services/auth.jsx';
import * as tracker from '../services/tracker.js';

/** Admin: everyone. Manager: their own team. */
export default function PeoplePage() {
  const { user } = useAuth();
  const toast = useToast();
  const isAdmin = user.role === 'admin';
  const [search, setSearch] = useState('');
  const [role, setRole] = useState('');
  const [status, setStatus] = useState('active');
  const [editing, setEditing] = useState(null); // user object, or 'new'
  const [confirm, setConfirm] = useState(null);
  const [confirmState, setConfirmState] = useState({ busy: false, error: '' });
  const [password, setPassword] = useState(null);
  const debouncedSearch = useDebounced(search);

  const people = useApi(
    () => tracker.listUsers({ search: debouncedSearch, role, status: isAdmin ? status : undefined }),
    [debouncedSearch, role, status, isAdmin],
  );

  const ask = (options) => {
    setConfirmState({ busy: false, error: '' });
    setConfirm(options);
  };
  const runConfirm = async () => {
    setConfirmState({ busy: true, error: '' });
    try {
      const result = await confirm.run();
      setConfirm(null);
      if (confirm.after) confirm.after(result);
      else toast(confirm.done);
      people.reload();
    } catch (error) {
      setConfirmState({ busy: false, error: error.message });
    }
  };

  const showSalary = people.data?.some((p) => p.salary !== undefined);

  return (
    <div className="page">
      <PageHead
        title={isAdmin ? 'People' : 'My team'}
        description={isAdmin
          ? 'Add people, set their role and manager, and archive people who have left. Archived people keep their history.'
          : 'Employees who report to you. You can update their details and salary; an admin adds or moves people.'}
        actions={isAdmin && (
          <button type="button" className="button button--primary" onClick={() => setEditing('new')}>Add person</button>
        )}
      />

      <div className="toolbar" role="search">
        <Field
          className="grow"
          label="Search"
          name="search"
          type="search"
          placeholder="Name, username, email or job"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
        {isAdmin && (
          <>
            <Field label="Role" name="role" as="select" value={role} onChange={(e) => setRole(e.target.value)}>
              <option value="">All roles</option>
              <option value="admin">Admins</option>
              <option value="manager">Managers</option>
              <option value="employee">Employees</option>
            </Field>
            <Field label="Show" name="status" as="select" value={status} onChange={(e) => setStatus(e.target.value)}>
              <option value="active">Active people</option>
              <option value="archived">Archived people</option>
              <option value="all">Everyone</option>
            </Field>
          </>
        )}
      </div>

      {people.error && <ErrorState error={people.error} onRetry={people.reload} />}
      {people.loading && !people.data && <Loading label="Loading people…" />}
      {people.data && people.data.length === 0 && (
        <EmptyState title={debouncedSearch || role || status !== 'active' ? 'Nobody matches these filters' : 'Nobody here yet'}>
          {isAdmin ? 'Add a person to get started.' : 'An admin assigns employees to managers.'}
        </EmptyState>
      )}
      {people.data && people.data.length > 0 && (
        <div className="table-wrap">
          <table className="table">
            <thead>
              <tr>
                <th scope="col">Person</th>
                {isAdmin && <th scope="col">Role</th>}
                <th scope="col">Job</th>
                {isAdmin && <th scope="col">Manager</th>}
                {showSalary && <th scope="col" className="right">Salary</th>}
                <th scope="col">Working on</th>
                <th scope="col" className="right">This week</th>
                <th scope="col"><span className="visually-hidden">Actions</span></th>
              </tr>
            </thead>
            <tbody>
              {people.data.map((p) => (
                <tr key={p.id} className={p.archived ? 'is-archived' : ''}>
                  <td>
                    <span className="cell-title">{p.name}</span>
                    <span className="cell-sub">{`${p.display_id}, ${p.username}`}</span>
                    <span className="cell-sub">{p.email}</span>
                  </td>
                  {isAdmin && <td><RolePill role={p.role} /></td>}
                  <td>{p.title || <span className="faint">–</span>}</td>
                  {isAdmin && <td>{p.manager_name || <span className="faint">–</span>}</td>}
                  {showSalary && (
                    <td className="right num">
                      {p.salary !== undefined ? formatMoney(p.salary) : ''}
                      {p.hourly_rate ? <span className="cell-sub">{`${formatMoney(p.hourly_rate, { cents: true })}/h`}</span> : null}
                    </td>
                  )}
                  <td>
                    {p.archived && <span className="pill pill--plain">{`Archived ${formatDate(p.archived_at?.slice(0, 10))}`}</span>}
                    {!p.archived && p.role === 'employee' && (p.current_assignment ? (
                      <>
                        <Link to={`/projects/${p.current_assignment.project_id}`}>{p.current_assignment.milestone_title}</Link>
                        <span className="cell-sub">{p.current_assignment.project_title}</span>
                      </>
                    ) : <span className="pill pill--amber">Unassigned</span>)}
                  </td>
                  <td className="right num">{p.role === 'employee' ? formatHours(p.hours_this_week) : ''}</td>
                  <td>
                    <div className="actions" style={{ justifyContent: 'flex-end', flexWrap: 'nowrap' }}>
                      {!p.archived && (
                        <button type="button" className="button button--small" onClick={() => setEditing(p)}>Edit</button>
                      )}
                      {isAdmin && !p.archived && p.id !== user.id && (
                        <>
                          <button
                            type="button"
                            className="button button--small"
                            onClick={() => ask({
                              title: `Reset ${p.name}'s password?`,
                              message: 'They will need the new temporary password to sign in.',
                              label: 'Reset password',
                              run: () => tracker.resetPassword(p.id),
                              after: (result) => setPassword({ name: p.name, value: result.temporary_password }),
                            })}
                          >
                            Reset password
                          </button>
                          <button
                            type="button"
                            className="button button--small button--danger"
                            onClick={() => ask({
                              title: `Archive ${p.name}?`,
                              message: 'They will no longer be able to sign in. Their logged hours and history are kept, and you can restore them later.',
                              label: 'Archive',
                              danger: true,
                              done: `${p.name} archived`,
                              run: () => tracker.archiveUser(p.id),
                            })}
                          >
                            Archive
                          </button>
                        </>
                      )}
                      {isAdmin && p.archived && (
                        <button
                          type="button"
                          className="button button--small"
                          onClick={() => ask({
                            title: `Restore ${p.name}?`,
                            message: 'They will be able to sign in again with their old password.',
                            label: 'Restore',
                            done: `${p.name} restored`,
                            run: () => tracker.restoreUser(p.id),
                          })}
                        >
                          Restore
                        </button>
                      )}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {editing && (
        <UserFormModal
          target={editing === 'new' ? null : editing}
          viewerRole={user.role}
          viewerId={user.id}
          onClose={() => setEditing(null)}
          onSaved={(saved) => {
            setEditing(null);
            toast(editing === 'new' ? `Added ${saved.name}` : `Saved ${saved.name}`);
            people.reload();
          }}
        />
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
      {password && (
        <Modal title="New temporary password" onClose={() => setPassword(null)}>
          <TemporaryPassword name={password.name} password={password.value} onDone={() => setPassword(null)} />
        </Modal>
      )}
    </div>
  );
}

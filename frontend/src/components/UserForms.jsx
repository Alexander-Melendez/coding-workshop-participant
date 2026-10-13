import { useState } from 'react';
import PropTypes from 'prop-types';
import Field from './Field.jsx';
import Modal from './Modal.jsx';
import { FormError } from './States.jsx';
import { useApi, useForm } from '../lib/hooks.js';
import {
  email, first, nonNegative, required, username,
} from '../lib/validators.js';
import { createUser, listUsers, updateUser } from '../services/tracker.js';

/** Shows a generated password once, with a copy button. */
export function TemporaryPassword({ name, password, onDone }) {
  const [copied, setCopied] = useState(false);
  const copy = async () => {
    try {
      await navigator.clipboard.writeText(password);
      setCopied(true);
    } catch {
      setCopied(false);
    }
  };
  return (
    <>
      <div className="banner banner--success">
        {`Share this temporary password with ${name}. It won't be shown again; they can change it from their profile.`}
      </div>
      <div className="secret">
        <span data-testid="temporary-password">{password}</span>
        <button type="button" className="button button--small" onClick={copy}>{copied ? 'Copied' : 'Copy'}</button>
      </div>
      <div className="modal-foot">
        <button type="button" className="button button--primary" onClick={onDone}>Done</button>
      </div>
    </>
  );
}

TemporaryPassword.propTypes = {
  name: PropTypes.string.isRequired,
  password: PropTypes.string.isRequired,
  onDone: PropTypes.func.isRequired,
};

/**
 * Create a user (admin) or edit one. Which fields appear depends on the
 * signed-in role: managers edit name, email, job title and salary of their team;
 * admins edit everything. Job title, salary and manager only apply to employees.
 */
export default function UserFormModal({
  target, viewerRole, viewerId, onClose, onSaved,
}) {
  const editing = Boolean(target);
  const isAdmin = viewerRole === 'admin';
  const canEditRole = isAdmin && (!editing || target.id !== viewerId);
  const managers = useApi(() => (isAdmin ? listUsers({ role: 'manager' }) : Promise.resolve([])), [isAdmin]);
  const [created, setCreated] = useState(null);

  const form = useForm(
    {
      name: target?.name ?? '',
      username: target?.username ?? '',
      email: target?.email ?? '',
      role: target?.role ?? 'employee',
      title: target?.title ?? '',
      salary: target?.salary !== undefined ? String(target.salary) : '',
      manager_id: target?.manager_id ? String(target.manager_id) : '',
    },
    (v) => ({
      name: required(v.name),
      username: isAdmin ? first(required(v.username), username(v.username)) : '',
      email: first(required(v.email), email(v.email)),
      salary: nonNegative(v.salary),
    }),
    async (v) => {
      const isEmployee = v.role === 'employee';
      const body = { name: v.name.trim(), email: v.email.trim() };
      if (isEmployee) {
        body.title = v.title.trim() || null;
        body.salary = v.salary === '' ? 0 : Number(v.salary);
      }
      if (isAdmin) {
        body.username = v.username.trim();
        if (canEditRole) body.role = v.role;
        if (isEmployee) body.manager_id = v.manager_id ? Number(v.manager_id) : null;
      }
      if (editing) {
        onSaved(await updateUser(target.id, body));
      } else {
        const result = await createUser(body);
        setCreated(result);
      }
    },
  );

  if (created) {
    return (
      <Modal title={`${created.user.name} can now sign in`} onClose={() => onSaved(created.user)}>
        <p className="small">
          {`Username `}
          <strong>{created.user.username}</strong>
          {`, ID ${created.user.display_id}.`}
        </p>
        <TemporaryPassword name={created.user.name} password={created.temporary_password} onDone={() => onSaved(created.user)} />
      </Modal>
    );
  }

  return (
    <Modal
      title={editing ? `Edit ${target.name}` : 'Add a person'}
      description={editing ? undefined : 'They get a random 6-character password to sign in with.'}
      onClose={onClose}
      wide
    >
      <form className="form" onSubmit={form.handleSubmit} noValidate>
        <div className="form-row">
          <Field label="Full name" required maxLength={120} autoComplete="off" {...form.field('name')} />
          <Field label="Email" type="email" required autoComplete="off" {...form.field('email')} />
        </div>
        {isAdmin && (
          <div className="form-row">
            <Field label="Username" required maxLength={40} autoComplete="off" hint="Used to sign in" {...form.field('username')} />
            <Field
              label="Role"
              as="select"
              disabled={!canEditRole}
              hint={!canEditRole && editing ? "You can't change your own role" : undefined}
              {...form.field('role')}
            >
              <option value="employee">Employee</option>
              <option value="manager">Manager</option>
              <option value="admin">Admin</option>
            </Field>
          </div>
        )}
        {form.values.role === 'employee' && (
          <div className="form-row">
            <Field label="Job title" maxLength={80} placeholder="e.g. Systems engineer" {...form.field('title')} />
            <Field
              label="Annual salary (USD)"
              type="number"
              min="0"
              step="1000"
              hint="Hourly cost is salary divided by 2,080"
              {...form.field('salary')}
            />
          </div>
        )}
        {isAdmin && form.values.role === 'employee' && (
          <Field label="Manager" as="select" hint="Each employee reports to one manager" {...form.field('manager_id')}>
            <option value="">No manager</option>
            {(managers.data || []).map((m) => <option key={m.id} value={m.id}>{`${m.name} (${m.display_id})`}</option>)}
          </Field>
        )}
        <FormError message={form.formError} />
        <div className="modal-foot">
          <button type="button" className="button" onClick={onClose}>Cancel</button>
          <button type="submit" className="button button--primary" disabled={form.submitting}>
            {form.submitting ? 'Saving…' : (editing ? 'Save changes' : 'Add person')}
          </button>
        </div>
      </form>
    </Modal>
  );
}

UserFormModal.propTypes = {
  target: PropTypes.shape({
    id: PropTypes.number,
    name: PropTypes.string,
    username: PropTypes.string,
    email: PropTypes.string,
    role: PropTypes.string,
    title: PropTypes.string,
    salary: PropTypes.oneOfType([PropTypes.number, PropTypes.string]),
    manager_id: PropTypes.number,
  }),
  viewerRole: PropTypes.string.isRequired,
  viewerId: PropTypes.number.isRequired,
  onClose: PropTypes.func.isRequired,
  onSaved: PropTypes.func.isRequired,
};

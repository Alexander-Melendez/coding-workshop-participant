import { PageHead } from '../components/Layout.jsx';
import Field from '../components/Field.jsx';
import { FormError } from '../components/States.jsx';
import { RolePill } from '../components/Pills.jsx';
import { useToast } from '../components/Toasts.jsx';
import { useForm } from '../lib/hooks.js';
import { formatMoney } from '../lib/format.js';
import {
  email, first, minLength, required,
} from '../lib/validators.js';
import { useAuth } from '../services/auth.jsx';
import { changePassword, updateMe } from '../services/tracker.js';

/** Your details: everyone can change their own name, email and password. */
export default function ProfilePage() {
  const { user, refreshUser } = useAuth();
  const toast = useToast();

  const details = useForm(
    { name: user.name, email: user.email },
    (v) => ({ name: required(v.name), email: first(required(v.email), email(v.email)) }),
    async (v) => {
      await updateMe({ name: v.name.trim(), email: v.email.trim() });
      await refreshUser();
      toast('Details saved');
    },
  );

  const password = useForm(
    { current_password: '', new_password: '', confirm: '' },
    (v) => ({
      current_password: required(v.current_password),
      new_password: first(required(v.new_password), minLength(8)(v.new_password)),
      confirm: v.confirm !== v.new_password ? "Passwords don't match" : '',
    }),
    async (v) => {
      await changePassword({ current_password: v.current_password, new_password: v.new_password });
      password.setValues({ current_password: '', new_password: '', confirm: '' });
      toast('Password changed');
    },
  );

  return (
    <div className="page">
      <PageHead title="Your profile" />
      <div className="split">
        <div className="stack stack--loose">
          <section className="panel" aria-labelledby="details-heading">
            <div className="panel-head"><h2 id="details-heading">Your details</h2></div>
            <form className="form" onSubmit={details.handleSubmit} noValidate>
              <Field label="Full name" required maxLength={120} autoComplete="name" {...details.field('name')} />
              <Field label="Email" type="email" required autoComplete="email" {...details.field('email')} />
              <FormError message={details.formError} />
              <div className="actions">
                <button type="submit" className="button button--primary" disabled={details.submitting}>
                  {details.submitting ? 'Saving…' : 'Save details'}
                </button>
              </div>
            </form>
          </section>

          <section className="panel" aria-labelledby="password-heading">
            <div className="panel-head"><h2 id="password-heading">Change password</h2></div>
            <form className="form" onSubmit={password.handleSubmit} noValidate>
              <Field label="Current password" type="password" autoComplete="current-password" required {...password.field('current_password')} />
              <div className="form-row">
                <Field label="New password" type="password" autoComplete="new-password" hint="At least 8 characters" required {...password.field('new_password')} />
                <Field label="Repeat new password" type="password" autoComplete="new-password" required {...password.field('confirm')} />
              </div>
              <FormError message={password.formError} />
              <div className="actions">
                <button type="submit" className="button button--primary" disabled={password.submitting}>
                  {password.submitting ? 'Saving…' : 'Change password'}
                </button>
              </div>
            </form>
          </section>
        </div>

        <section className="panel" aria-labelledby="account-heading">
          <div className="panel-head"><h2 id="account-heading">Account</h2></div>
          <dl className="definition">
            <dt>ID</dt>
            <dd>{user.display_id}</dd>
            <dt>Username</dt>
            <dd>{user.username}</dd>
            <dt>Role</dt>
            <dd><RolePill role={user.role} /></dd>
            {user.title && (
              <>
                <dt>Job</dt>
                <dd>{user.title}</dd>
              </>
            )}
            {user.role === 'employee' && (
              <>
                <dt>Manager</dt>
                <dd>{user.manager_name || 'None'}</dd>
              </>
            )}
            {user.salary !== undefined && user.role !== 'admin' && (
              <>
                <dt>Salary</dt>
                <dd>{formatMoney(user.salary)}</dd>
              </>
            )}
          </dl>
          <p className="faint small" style={{ marginTop: 'var(--s4)' }}>
            {user.role === 'admin'
              ? 'Admins change roles, usernames and salaries on the People page.'
              : 'Ask your manager or an admin to change your job, salary or manager.'}
          </p>
        </section>
      </div>
    </div>
  );
}

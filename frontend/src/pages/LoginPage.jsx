import { useEffect } from 'react';
import Field from '../components/Field.jsx';
import { FormError } from '../components/States.jsx';
import { useForm } from '../lib/hooks.js';
import { required } from '../lib/validators.js';
import { useAuth } from '../services/auth.jsx';

/** Sign-in screen. */
export default function LoginPage() {
  const { login, notice } = useAuth();
  const form = useForm(
    { username: '', password: '' },
    (v) => ({ username: required(v.username), password: required(v.password) }),
    (v) => login(v.username.trim(), v.password),
  );

  useEffect(() => {
    document.title = 'Sign in | ACME Project Tracker';
  }, []);

  return (
    <div className="login">
      <section className="login-art" aria-hidden="true">
        <div>
          <h1>Every project, on one sheet.</h1>
          <p>
            See which projects are on track, which have run over budget and which are done,
            then drill into milestones, people and hours.
          </p>
        </div>
        <div className="login-sheets">
          <div style={{ background: '#fff', color: '#1d2433', borderColor: '#1d2433' }}>In progress</div>
          <div style={{ background: '#fbe9e7', color: '#c4342d', borderColor: '#c4342d' }}>Over budget</div>
          <div style={{ background: '#e6f2ea', color: '#2f7d4f', borderColor: '#2f7d4f' }}>Completed</div>
        </div>
      </section>

      <section className="login-form">
        <div>
          <h2>Sign in to ACME Project Tracker</h2>
          <p className="muted small">Use the username or email and password your admin gave you.</p>
        </div>
        {notice && <div className="banner banner--info">{notice}</div>}
        <form className="form" onSubmit={form.handleSubmit} noValidate>
          <Field label="Username or email" autoComplete="username" required {...form.field('username')} />
          <Field label="Password" type="password" autoComplete="current-password" required {...form.field('password')} />
          <FormError message={form.formError} />
          <button type="submit" className="button button--primary" disabled={form.submitting}>
            {form.submitting ? 'Signing in…' : 'Sign in'}
          </button>
        </form>
        {import.meta.env?.DEV && (
          <p className="faint small">
            Local setup: the first admin is
            {' '}
            <strong>admin</strong>
            {' / '}
            <strong>Admin@123</strong>
            . Change it on your profile after signing in.
          </p>
        )}
      </section>
    </div>
  );
}

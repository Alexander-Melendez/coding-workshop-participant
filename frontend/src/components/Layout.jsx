import { useEffect, useState } from 'react';
import PropTypes from 'prop-types';
import { Link, useRouter } from '../lib/router.jsx';
import { useAuth } from '../services/auth.jsx';
import { roleLabel } from '../lib/format.js';
import Logo from './Logo.jsx';

/** Navigation per role: each role sees only the pages it can use. */
export const NAV = {
  admin: [
    { to: '/', label: 'Overview' },
    { to: '/projects', label: 'Projects' },
    { to: '/people', label: 'People' },
    { to: '/time', label: 'Timesheets' },
    { to: '/audit', label: 'Audit log' },
  ],
  manager: [
    { to: '/', label: 'Overview' },
    { to: '/projects', label: 'My projects' },
    { to: '/people', label: 'My team' },
    { to: '/time', label: 'Timesheets' },
  ],
  employee: [
    { to: '/', label: 'My week' },
    { to: '/time', label: 'Log time' },
    { to: '/projects', label: 'My projects' },
    { to: '/team', label: 'My team' },
  ],
};

function isActive(to, pathname) {
  return to === '/' ? pathname === '/' : pathname === to || pathname.startsWith(`${to}/`);
}

/** Sidebar on desktop, slide-out drawer on phones. */
export default function Layout({ children }) {
  const { user, signOut } = useAuth();
  const { pathname } = useRouter();
  const [open, setOpen] = useState(false);

  useEffect(() => setOpen(false), [pathname]);

  return (
    <div className="shell">
      <header className="topbar">
        <button
          type="button"
          className="icon-button"
          aria-label="Open navigation"
          aria-expanded={open}
          onClick={() => setOpen(true)}
        >
          ☰
        </button>
        <span className="brand brand--bar"><Logo size={18} /><strong>Hexpath <span className="brand-pt">PT</span></strong></span>
      </header>
      {open && <div className="scrim" onClick={() => setOpen(false)} aria-hidden="true" />}

      <aside className="sidebar" data-open={open} aria-label="Main navigation">
        <div className="brand">
          <Logo />
          <strong>Hexpath <span className="brand-pt">PT</span></strong>
          <span>by ACME</span>
        </div>
        <nav className="nav">
          {(NAV[user.role] || []).map((item) => (
            <Link
              key={item.to}
              to={item.to}
              aria-current={isActive(item.to, pathname) ? 'page' : undefined}
            >
              {item.label}
            </Link>
          ))}
        </nav>
        <div className="sidebar-foot">
          <Link to="/profile" className="whoami">{user.name}</Link>
          <span className="whoami-role">{`${roleLabel(user.role)}, ${user.display_id}`}</span>
          <button type="button" className="link-button" onClick={() => signOut()}>Sign out</button>
        </div>
      </aside>

      <main className="main" id="main">{children}</main>
    </div>
  );
}

Layout.propTypes = { children: PropTypes.node.isRequired };

/** Standard page heading with optional description and actions. */
export function PageHead({ title, description, actions }) {
  useEffect(() => {
    document.title = `${title} | Hexpath PT`;
  }, [title]);
  return (
    <div className="page-head">
      <div>
        <h1>{title}</h1>
        {description && <p>{description}</p>}
      </div>
      {actions && <div className="actions">{actions}</div>}
    </div>
  );
}

PageHead.propTypes = {
  title: PropTypes.string.isRequired,
  description: PropTypes.node,
  actions: PropTypes.node,
};

import { RouterProvider, useRouter } from './lib/router.jsx';
import { resolveRoute } from './lib/routes.js';
import { AuthProvider, useAuth } from './services/auth.jsx';
import { ToastProvider } from './components/Toasts.jsx';
import Layout from './components/Layout.jsx';
import { Loading } from './components/States.jsx';
import LoginPage from './pages/LoginPage.jsx';
import DashboardPage from './pages/DashboardPage.jsx';
import ProjectsPage from './pages/ProjectsPage.jsx';
import ProjectDetailPage from './pages/ProjectDetailPage.jsx';
import PeoplePage from './pages/PeoplePage.jsx';
import TimePage from './pages/TimePage.jsx';
import AuditLogPage from './pages/AuditLogPage.jsx';
import ProfilePage from './pages/ProfilePage.jsx';
import MyTeamPage from './pages/MyTeamPage.jsx';
import NotFoundPage from './pages/NotFoundPage.jsx';

/**
 * Routes and the roles allowed on each. Hiding a page here is a UX choice;
 * the API enforces the same rules on every request.
 */
const ROUTES = [
  { path: '/', component: DashboardPage },
  { path: '/projects', component: ProjectsPage },
  { path: '/projects/:id', component: ProjectDetailPage },
  { path: '/people', component: PeoplePage, roles: ['admin', 'manager'] },
  { path: '/team', component: MyTeamPage, roles: ['employee'] },
  { path: '/time', component: TimePage },
  { path: '/audit', component: AuditLogPage, roles: ['admin'] },
  { path: '/profile', component: ProfilePage },
];

function CurrentPage() {
  const { user, status } = useAuth();
  const { pathname } = useRouter();

  if (status === 'loading') return <Loading label="Signing you in…" />;
  if (!user) return <LoginPage />;

  const match = resolveRoute(ROUTES, pathname);
  const allowed = match && (!match.route.roles || match.route.roles.includes(user.role));
  const Page = allowed ? match.route.component : NotFoundPage;
  return (
    <Layout>
      <Page params={match?.params || {}} />
    </Layout>
  );
}

/** Root component: providers + current page. */
export default function App() {
  return (
    <RouterProvider>
      <ToastProvider>
        <AuthProvider>
          <CurrentPage />
        </AuthProvider>
      </ToastProvider>
    </RouterProvider>
  );
}

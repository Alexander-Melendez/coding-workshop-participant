import { Link } from '../lib/router.jsx';
import { PageHead } from '../components/Layout.jsx';
import { EmptyState } from '../components/States.jsx';

/** Unknown path, or a page this role can't open. */
export default function NotFoundPage() {
  return (
    <div className="page">
      <PageHead title="Page not found" />
      <EmptyState
        title="This page doesn't exist or isn't available to your role"
        action={<Link className="button button--primary" to="/">Go to overview</Link>}
      />
    </div>
  );
}

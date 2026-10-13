import { useState } from 'react';
import { PageHead } from '../components/Layout.jsx';
import { ProjectSheets } from '../components/ProjectSheet.jsx';
import ProjectFormModal from '../components/ProjectForm.jsx';
import Field from '../components/Field.jsx';
import { EmptyState, ErrorState, Loading } from '../components/States.jsx';
import { useToast } from '../components/Toasts.jsx';
import { useApi, useDebounced } from '../lib/hooks.js';
import { useRouter } from '../lib/router.jsx';
import { useAuth } from '../services/auth.jsx';
import { listProjects } from '../services/tracker.js';

const HEALTH_FILTERS = [
  { value: '', label: 'All' },
  { value: 'white', label: 'In progress' },
  { value: 'red', label: 'Over budget' },
  { value: 'green', label: 'Completed' },
];

/** All projects the user can see, with search and filters. */
export default function ProjectsPage() {
  const { user } = useAuth();
  const { query, navigate } = useRouter();
  const toast = useToast();
  const isAdmin = user.role === 'admin';

  const [search, setSearch] = useState('');
  const [status, setStatus] = useState('');
  const [health, setHealth] = useState('');
  const [atRisk, setAtRisk] = useState(false);
  const [creating, setCreating] = useState(query.get('new') === '1' && isAdmin);
  const debouncedSearch = useDebounced(search);

  const { data, error, loading, reload } = useApi(
    () => listProjects({
      search: debouncedSearch, status, health, at_risk: atRisk,
    }),
    [debouncedSearch, status, health, atRisk],
  );

  const filtered = Boolean(debouncedSearch || status || health || atRisk);
  const title = { admin: 'Projects', manager: 'My projects', employee: 'My projects' }[user.role];
  const description = {
    admin: 'Every project in the company. White sheets are in progress, red are over budget, green are completed.',
    manager: 'Projects you manage. Open one to edit milestones, budget and assignments.',
    employee: 'Projects you are assigned to.',
  }[user.role];

  return (
    <div className="page">
      <PageHead
        title={title}
        description={description}
        actions={isAdmin && (
          <button type="button" className="button button--primary" onClick={() => setCreating(true)}>New project</button>
        )}
      />

      <div className="toolbar" role="search">
        <Field
          className="grow"
          label="Search"
          name="search"
          type="search"
          placeholder="Project name or description"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
        <Field label="Status" name="status" as="select" value={status} onChange={(e) => setStatus(e.target.value)}>
          <option value="">Open (active and completed)</option>
          <option value="active">Active</option>
          <option value="completed">Completed</option>
          {isAdmin && <option value="archived">Archived</option>}
          {isAdmin && <option value="all">Everything</option>}
        </Field>
        <div className="field">
          <span className="small" style={{ fontWeight: 600 }} id="health-label">Budget health</span>
          <div className="segmented" role="group" aria-labelledby="health-label">
            {HEALTH_FILTERS.map((f) => (
              <button key={f.value} type="button" aria-pressed={health === f.value} onClick={() => setHealth(f.value)}>
                {f.label}
              </button>
            ))}
          </div>
        </div>
        <label className="check" style={{ minHeight: 38 }}>
          <input type="checkbox" checked={atRisk} onChange={(e) => setAtRisk(e.target.checked)} />
          At risk only
        </label>
      </div>

      {error && <ErrorState error={error} onRetry={reload} />}
      {loading && !data && <Loading label="Loading projects…" />}
      {data && data.length > 0 && <ProjectSheets projects={data} />}
      {data && data.length === 0 && (
        filtered ? (
          <EmptyState title="No projects match these filters">Try a different search or clear the filters.</EmptyState>
        ) : (
          <EmptyState
            title="No projects yet"
            action={isAdmin && (
              <button type="button" className="button button--primary" onClick={() => setCreating(true)}>Create the first project</button>
            )}
          >
            {isAdmin ? 'Create a project and choose its manager.' : 'Projects you are part of will show up here.'}
          </EmptyState>
        )
      )}

      {creating && (
        <ProjectFormModal
          onClose={() => setCreating(false)}
          onSaved={(project) => {
            setCreating(false);
            toast(`Created ${project.title}`);
            navigate(`/projects/${project.id}`);
          }}
        />
      )}
    </div>
  );
}

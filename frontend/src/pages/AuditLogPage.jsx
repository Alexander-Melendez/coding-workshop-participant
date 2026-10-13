import { useState } from 'react';
import PropTypes from 'prop-types';
import { PageHead } from '../components/Layout.jsx';
import Field from '../components/Field.jsx';
import { EmptyState, ErrorState, Loading } from '../components/States.jsx';
import { useApi, useDebounced } from '../lib/hooks.js';
import { formatDateTime } from '../lib/format.js';
import { listAuditLogs } from '../services/tracker.js';

const PAGE_SIZE = 50;

function show(value) {
  if (value === null || value === undefined || value === '') return '(empty)';
  if (typeof value === 'object') return JSON.stringify(value);
  return String(value);
}

/** Before/after values for an audit entry. */
function Changes({ changes }) {
  if (!changes) return null;
  const keys = Object.keys(changes.after || changes.before || {});
  if (!keys.length) return null;
  return (
    <details className="changes">
      <summary>{`${keys.length} field${keys.length === 1 ? '' : 's'}`}</summary>
      <table>
        <tbody>
          {keys.map((key) => (
            <tr key={key}>
              <th scope="row">{key}</th>
              {changes.before && <td className="before">{show(changes.before[key])}</td>}
              {changes.after && <td className="after">{show(changes.after[key])}</td>}
            </tr>
          ))}
        </tbody>
      </table>
    </details>
  );
}

Changes.propTypes = { changes: PropTypes.shape({ before: PropTypes.object, after: PropTypes.object }) };

/** Admin-only, read-only record of every action in the app. */
export default function AuditLogPage() {
  const [search, setSearch] = useState('');
  const [action, setAction] = useState('');
  const [entity, setEntity] = useState('');
  const [from, setFrom] = useState('');
  const [to, setTo] = useState('');
  const [offset, setOffset] = useState(0);
  const debouncedSearch = useDebounced(search);

  const logs = useApi(
    () => listAuditLogs({
      search: debouncedSearch, action, entity_type: entity, date_from: from, date_to: to, limit: PAGE_SIZE, offset,
    }),
    [debouncedSearch, action, entity, from, to, offset],
  );
  const reset = (setter) => (e) => {
    setter(e.target.value);
    setOffset(0);
  };
  const data = logs.data;

  return (
    <div className="page">
      <PageHead
        title="Audit log"
        description="Every sign-in and change, who made it and when. Entries can't be edited or deleted."
      />
      <div className="toolbar" role="search">
        <Field className="grow" label="Search" name="search" type="search" placeholder="Description or person" value={search} onChange={reset(setSearch)} />
        <Field label="Action" name="action" as="select" value={action} onChange={reset(setAction)}>
          <option value="">All actions</option>
          {(data?.actions || []).map((a) => <option key={a} value={a}>{a.replace(/_/g, ' ')}</option>)}
        </Field>
        <Field label="Record" name="entity" as="select" value={entity} onChange={reset(setEntity)}>
          <option value="">All records</option>
          {(data?.entity_types || []).map((t) => <option key={t} value={t}>{t.replace(/_/g, ' ')}</option>)}
        </Field>
        <Field label="From" name="from" type="date" value={from} onChange={reset(setFrom)} />
        <Field label="To" name="to" type="date" value={to} onChange={reset(setTo)} />
      </div>

      {logs.error && <ErrorState error={logs.error} onRetry={logs.reload} />}
      {logs.loading && !data && <Loading label="Loading audit log…" />}
      {data && data.items.length === 0 && <EmptyState title="No entries match these filters" />}
      {data && data.items.length > 0 && (
        <>
          <div className="table-wrap">
            <table className="table">
              <thead>
                <tr>
                  <th scope="col">When</th>
                  <th scope="col">Who</th>
                  <th scope="col">Action</th>
                  <th scope="col">What happened</th>
                </tr>
              </thead>
              <tbody>
                {data.items.map((row) => (
                  <tr key={row.id}>
                    <td className="nowrap">{formatDateTime(row.created_at)}</td>
                    <td>
                      {row.actor_name || <span className="faint">{row.action === 'login_failed' ? 'Unknown' : 'System'}</span>}
                      {row.actor_display_id && <span className="cell-sub">{row.actor_display_id}</span>}
                    </td>
                    <td>
                      <span className={`pill pill--plain ${row.action === 'login_failed' ? 'pill--red' : ''}`}>
                        {row.action.replace(/_/g, ' ')}
                      </span>
                    </td>
                    <td>
                      {row.summary}
                      <Changes changes={row.changes} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div className="pager">
            <span>{`${offset + 1}–${offset + data.items.length} of ${data.total}`}</span>
            <div className="actions">
              <button type="button" className="button button--small" disabled={offset === 0} onClick={() => setOffset(Math.max(0, offset - PAGE_SIZE))}>Newer</button>
              <button type="button" className="button button--small" disabled={offset + PAGE_SIZE >= data.total} onClick={() => setOffset(offset + PAGE_SIZE)}>Older</button>
            </div>
          </div>
        </>
      )}
    </div>
  );
}

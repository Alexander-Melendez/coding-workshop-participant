import {
  useEffect, useRef, useState,
} from 'react';
import PropTypes from 'prop-types';
import { PageHead } from '../components/Layout.jsx';
import Field from '../components/Field.jsx';
import { EmptyState, ErrorState, Loading } from '../components/States.jsx';
import { useApi, useDebounced } from '../lib/hooks.js';
import { formatDateTime } from '../lib/format.js';
import { listAuditLogs } from '../services/tracker.js';

const PAGE_SIZE = 50;
const LIVE_EVERY_MS = 5000;   // how often the live tail checks for new entries
const NEW_FOR_MS = 8000;      // how long a new entry stays highlighted

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

/**
 * Live tail: while on the newest page, re-check every few seconds (like
 * `tail -f`). Entries that arrive are highlighted light blue for a few
 * seconds, then fade. Pauses on older pages and while the tab is hidden.
 */
function useLiveTail(logs, queryKey, enabled) {
  const [fresh, setFresh] = useState(() => new Set());
  const [announcement, setAnnouncement] = useState('');
  const lastSeen = useRef({ key: null, maxId: 0 });
  const timers = useRef([]);

  useEffect(() => {
    if (!enabled) return undefined;
    const id = setInterval(() => {
      if (!document.hidden) logs.reload();
    }, LIVE_EVERY_MS);
    return () => clearInterval(id);
  }, [enabled, logs.reload]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => () => timers.current.forEach(clearTimeout), []);

  const data = logs.data;
  useEffect(() => {
    if (!data) return;
    const maxId = data.items.reduce((max, row) => Math.max(max, row.id), 0);
    const prev = lastSeen.current;
    // Only entries newer than what this same search already showed count as new;
    // changing a filter or page just shows a different set of rows.
    const sameQuery = prev.key === data.query;
    if (sameQuery) {
      const added = data.items.filter((row) => row.id > prev.maxId).map((row) => row.id);
      if (added.length) {
        setFresh((current) => new Set([...current, ...added]));
        setAnnouncement(`${added.length} new ${added.length === 1 ? 'entry' : 'entries'}`);
        timers.current.push(setTimeout(() => {
          setFresh((current) => {
            const next = new Set(current);
            added.forEach((id) => next.delete(id));
            return next;
          });
        }, NEW_FOR_MS));
      }
    }
    lastSeen.current = { key: data.query, maxId: sameQuery ? Math.max(maxId, prev.maxId) : maxId };
  }, [data]);

  return { fresh, announcement };
}

/** Admin-only, read-only record of every action in the app. */
export default function AuditLogPage() {
  const [search, setSearch] = useState('');
  const [action, setAction] = useState('');
  const [entity, setEntity] = useState('');
  const [from, setFrom] = useState('');
  const [to, setTo] = useState('');
  const [offset, setOffset] = useState(0);
  const [live, setLive] = useState(true);
  const debouncedSearch = useDebounced(search);
  const queryKey = JSON.stringify([debouncedSearch, action, entity, from, to, offset]);

  const logs = useApi(
    () => listAuditLogs({
      search: debouncedSearch, action, entity_type: entity, date_from: from, date_to: to, limit: PAGE_SIZE, offset,
    }).then((result) => ({ ...result, query: queryKey })),
    [queryKey],
  );
  const tailing = live && offset === 0;
  const { fresh, announcement } = useLiveTail(logs, queryKey, tailing);
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
        actions={(
          <div className="live">
            <span className={`live-status ${tailing ? 'is-on' : ''}`}>
              <span className="live-dot" aria-hidden="true" />
              {tailing ? 'Live' : (live ? 'Live on newest page only' : 'Paused')}
            </span>
            <button type="button" className="button button--small" onClick={() => setLive(!live)} aria-pressed={!live}>
              {live ? 'Pause' : 'Resume'}
            </button>
          </div>
        )}
      />
      <div className="visually-hidden" aria-live="polite">{announcement}</div>
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
                  <tr key={row.id} className={fresh.has(row.id) ? 'is-new' : undefined}>
                    <td className="nowrap">
                      {formatDateTime(row.created_at)}
                      {fresh.has(row.id) && <span className="new-tag">New</span>}
                    </td>
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

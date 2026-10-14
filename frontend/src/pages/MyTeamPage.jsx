import PropTypes from 'prop-types';
import { PageHead } from '../components/Layout.jsx';
import { EmptyState, ErrorState, Loading } from '../components/States.jsx';
import { useApi } from '../lib/hooks.js';
import { getMyTeam } from '../services/tracker.js';

/**
 * Employees: their manager and immediate team (everyone with the same
 * manager). Contact details only; the API leaves out salaries and work.
 */
export default function MyTeamPage() {
  const team = useApi(() => getMyTeam(), []);

  return (
    <div className="page">
      <PageHead title="My team" description="Your manager and the people who report to them." />
      {team.error && <ErrorState error={team.error} onRetry={team.reload} />}
      {team.loading && !team.data && <Loading />}
      {team.data && !team.data.manager && (
        <EmptyState title="You don't have a manager yet">An admin assigns each employee to a manager.</EmptyState>
      )}
      {team.data?.manager && (
        <div className="stack stack--loose">
          <section className="panel" aria-labelledby="manager-heading">
            <div className="panel-head"><h2 id="manager-heading">Manager</h2></div>
            <dl className="definition">
              <dt>Name</dt>
              <dd>{team.data.manager.name}</dd>
              <dt>ID</dt>
              <dd>{team.data.manager.display_id}</dd>
              <dt>Email</dt>
              <dd><a href={`mailto:${team.data.manager.email}`}>{team.data.manager.email}</a></dd>
            </dl>
          </section>

          <section className="panel" aria-labelledby="team-heading">
            <div className="panel-head">
              <h2 id="team-heading">Team</h2>
              <p>{`${team.data.teammates.length} ${team.data.teammates.length === 1 ? 'person' : 'people'}`}</p>
            </div>
            <TeammateTable teammates={team.data.teammates} />
          </section>
        </div>
      )}
    </div>
  );
}

function TeammateTable({ teammates }) {
  return (
    <div className="table-wrap">
      <table className="table">
        <thead>
          <tr>
            <th scope="col">Name</th>
            <th scope="col">Job</th>
            <th scope="col">Email</th>
          </tr>
        </thead>
        <tbody>
          {teammates.map((person) => (
            <tr key={person.id}>
              <td>
                <span className="cell-title">{person.is_me ? `${person.name} (you)` : person.name}</span>
                <span className="cell-sub">{person.display_id}</span>
              </td>
              <td>{person.title || <span className="faint">None</span>}</td>
              <td><a href={`mailto:${person.email}`}>{person.email}</a></td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

TeammateTable.propTypes = {
  teammates: PropTypes.arrayOf(PropTypes.shape({
    id: PropTypes.number.isRequired,
    display_id: PropTypes.string.isRequired,
    name: PropTypes.string.isRequired,
    email: PropTypes.string.isRequired,
    title: PropTypes.string,
    is_me: PropTypes.bool,
  })).isRequired,
};

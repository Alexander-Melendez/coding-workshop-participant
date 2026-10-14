import PropTypes from 'prop-types';
import { layoutMilestones } from '../lib/graph.js';

const COL_W = 168;   // width of one column
const ROW_H = 76;    // height of one row
const TOP = 18;      // centre of the first row's diamond
const PAD = 8;

/**
 * Overview strip above the milestone list: each milestone is a diamond on
 * the path, joined to what it depends on. Same diamonds and colours as the
 * list below. Clicking one jumps to its row.
 */
export default function MilestoneGraph({ milestones }) {
  const { nodes, edges, columns, rows } = layoutMilestones(milestones);
  const at = new Map(nodes.map((n) => [n.id, {
    x: PAD + n.col * COL_W + COL_W / 2,
    y: TOP + n.row * ROW_H,
  }]));
  const width = PAD * 2 + columns * COL_W;
  const height = TOP + (rows - 1) * ROW_H + 50;

  const jumpTo = (id) => {
    const row = document.getElementById(`milestone-${id}`);
    if (!row) return;
    row.scrollIntoView({ behavior: 'smooth', block: 'center' });
    row.focus({ preventScroll: true });
  };

  return (
    <div className="mgraph" role="group" aria-label="Milestone path">
      <div className="mgraph-canvas" style={{ width, height }}>
        <svg className="mgraph-edges" width={width} height={height} aria-hidden="true">
          {edges.map((e) => {
            const a = at.get(e.from);
            const b = at.get(e.to);
            const x1 = a.x + 12;
            const x2 = b.x - 12;
            const bend = (x2 - x1) / 2;
            return (
              <path
                key={`${e.from}-${e.to}`}
                className={e.done ? 'is-done' : undefined}
                d={`M${x1} ${a.y} C${x1 + bend} ${a.y} ${x2 - bend} ${b.y} ${x2} ${b.y}`}
              />
            );
          })}
        </svg>
        {nodes.map((n) => {
          const { x, y } = at.get(n.id);
          return (
            <button
              key={n.id}
              type="button"
              className={`mgraph-node mgraph-node--${n.state}`}
              style={{ left: x - COL_W / 2 + 6, top: y - 10, width: COL_W - 12 }}
              onClick={() => jumpTo(n.id)}
              title={`${n.title}: ${n.label}`}
            >
              <span className={`milestone-mark milestone-mark--${n.state}`} aria-hidden="true" />
              <span className="mgraph-title">{n.title}</span>
              <span className="mgraph-state">{n.label}</span>
            </button>
          );
        })}
      </div>
    </div>
  );
}

MilestoneGraph.propTypes = {
  milestones: PropTypes.arrayOf(PropTypes.shape({
    id: PropTypes.number.isRequired,
    title: PropTypes.string.isRequired,
    status: PropTypes.string.isRequired,
    overdue: PropTypes.bool,
    start_date: PropTypes.string,
    depends_on: PropTypes.arrayOf(PropTypes.shape({ id: PropTypes.number, complete: PropTypes.bool })),
    waiting_on: PropTypes.arrayOf(PropTypes.string),
  })).isRequired,
};

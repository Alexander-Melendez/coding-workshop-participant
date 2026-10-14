import PropTypes from 'prop-types';
import Field from './Field.jsx';
import Modal from './Modal.jsx';
import { FormError } from './States.jsx';
import { useApi, useForm } from '../lib/hooks.js';
import {
  formatDate, parseDate, toISODate, todayISO,
} from '../lib/format.js';
import {
  dateOrder, first, readyAfter, required, startsAfterPredecessors,
} from '../lib/validators.js';
import {
  createAssignment, createMilestone, listUsers, updateMilestone,
} from '../services/tracker.js';

function withinMessage(value, start, end) {
  if (value && start && value < start) return `Must be on or after ${formatDate(start)}`;
  if (value && end && value > end) return `Must be on or before ${formatDate(end)}`;
  return '';
}

function dayAfter(iso) {
  const day = parseDate(iso);
  day.setDate(day.getDate() + 1);
  return toISODate(day);
}

/**
 * Add or edit a milestone. Dates must fall inside the project's dates.
 * Status comes from the dates and completed_at, so there's nothing to pick.
 * The description is the completion criteria ("200 servers retired").
 * A milestone can depend on others in the project and must start after they end.
 */
export function MilestoneFormModal({
  project, milestone, milestones = [], onClose, onSaved,
}) {
  const editing = Boolean(milestone);
  const others = milestones.filter((m) => m.id !== milestone?.id);
  const form = useForm(
    {
      title: milestone?.title ?? '',
      description: milestone?.description ?? '',
      start_date: milestone?.start_date ?? project.start_date,
      end_date: milestone?.end_date ?? '',
      depends_on: (milestone?.depends_on ?? []).map((d) => d.id),
    },
    (v) => ({
      title: required(v.title),
      description: required(v.description),
      start_date: first(
        required(v.start_date),
        withinMessage(v.start_date, project.start_date, project.end_date),
        startsAfterPredecessors(v.start_date, others.filter((m) => v.depends_on.includes(m.id))),
      ),
      end_date: first(
        required(v.end_date),
        dateOrder(v.start_date, v.end_date),
        withinMessage(v.end_date, project.start_date, project.end_date),
      ),
    }),
    async (v) => {
      const body = {
        title: v.title.trim(),
        description: v.description.trim(),
        start_date: v.start_date,
        end_date: v.end_date,
        depends_on: v.depends_on,
      };
      const saved = editing ? await updateMilestone(milestone.id, body) : await createMilestone(project.id, body);
      onSaved(saved);
    },
  );

  const toggleDependency = (other, checked) => {
    form.setValue('depends_on', checked
      ? [...form.values.depends_on, other.id]
      : form.values.depends_on.filter((id) => id !== other.id));
    // Picking a predecessor moves the start to the day after it ends, if needed
    const ready = readyAfter(other);
    if (checked && form.values.start_date <= ready) {
      const start = dayAfter(ready);
      form.setValue('start_date', start);
      if (form.values.end_date && form.values.end_date < start) form.setValue('end_date', '');
    }
  };

  return (
    <Modal
      title={editing ? 'Edit milestone' : 'Add milestone'}
      description={`Between ${formatDate(project.start_date)} and ${formatDate(project.end_date)}. Completed milestones can't be changed.`}
      onClose={onClose}
    >
      <form className="form" onSubmit={form.handleSubmit} noValidate>
        <Field label="Title" required maxLength={150} placeholder="e.g. First 200 servers" {...form.field('title')} />
        <Field
          label="Completion criteria"
          as="textarea"
          required
          maxLength={2000}
          placeholder="e.g. Complete the first 200 problems"
          hint="What has to be done for this milestone to count as complete. Put the full instructions in the project description."
          {...form.field('description')}
        />
        {others.length > 0 && (
          <fieldset className="field">
            <legend>Depends on</legend>
            <div className="checks">
              {others.map((other) => (
                <label key={other.id} className="check">
                  <input
                    type="checkbox"
                    checked={form.values.depends_on.includes(other.id)}
                    onChange={(event) => toggleDependency(other, event.target.checked)}
                  />
                  {other.title}
                  <span className="faint small">
                    {other.completed_at ? 'complete' : `ends ${formatDate(other.end_date, { withYear: false })}`}
                  </span>
                </label>
              ))}
            </div>
            {form.errors.depends_on
              ? <span className="field-error">{form.errors.depends_on}</span>
              : <span className="field-hint">It can't start, log hours or be completed until these are complete.</span>}
          </fieldset>
        )}
        <div className="form-row">
          <Field label="Start date" type="date" min={project.start_date} max={project.end_date} required {...form.field('start_date')} />
          <Field label="End date" type="date" min={project.start_date} max={project.end_date} required {...form.field('end_date')} />
        </div>
        <FormError message={form.formError} />
        <div className="modal-foot">
          <button type="button" className="button" onClick={onClose}>Cancel</button>
          <button type="submit" className="button button--primary" disabled={form.submitting}>
            {form.submitting ? 'Saving…' : (editing ? 'Save milestone' : 'Add milestone')}
          </button>
        </div>
      </form>
    </Modal>
  );
}

MilestoneFormModal.propTypes = {
  project: PropTypes.shape({
    id: PropTypes.number.isRequired,
    start_date: PropTypes.string.isRequired,
    end_date: PropTypes.string.isRequired,
  }).isRequired,
  milestone: PropTypes.shape({
    id: PropTypes.number.isRequired,
    title: PropTypes.string.isRequired,
    description: PropTypes.string,
    start_date: PropTypes.string.isRequired,
    end_date: PropTypes.string.isRequired,
    depends_on: PropTypes.arrayOf(PropTypes.shape({ id: PropTypes.number.isRequired })),
  }),
  milestones: PropTypes.arrayOf(PropTypes.shape({
    id: PropTypes.number.isRequired,
    title: PropTypes.string.isRequired,
    end_date: PropTypes.string.isRequired,
    completed_at: PropTypes.string,
  })),
  onClose: PropTypes.func.isRequired,
  onSaved: PropTypes.func.isRequired,
};

/**
 * Put an employee on a milestone. Employees work on one milestone at a time,
 * so the list shows who is busy and the API rejects overlapping dates.
 */
export function AssignModal({
  milestone, isAdmin, onClose, onSaved,
}) {
  const people = useApi(() => listUsers(isAdmin ? { role: 'employee' } : {}), [isAdmin]);
  const today = todayISO();
  let defaultStart = milestone.start_date > today ? milestone.start_date : today;
  if (defaultStart > milestone.end_date) defaultStart = milestone.start_date;

  const form = useForm(
    { user_id: '', start_date: defaultStart, end_date: milestone.end_date },
    (v) => ({
      user_id: required(v.user_id),
      start_date: first(required(v.start_date), withinMessage(v.start_date, milestone.start_date, milestone.end_date)),
      end_date: first(
        required(v.end_date),
        dateOrder(v.start_date, v.end_date),
        withinMessage(v.end_date, milestone.start_date, milestone.end_date),
      ),
    }),
    async (v) => {
      const saved = await createAssignment(milestone.id, {
        user_id: Number(v.user_id), start_date: v.start_date, end_date: v.end_date,
      });
      onSaved(saved);
    },
  );

  const assignedIds = new Set(milestone.assignments.map((a) => a.user_id));
  const describe = (p) => {
    if (assignedIds.has(p.id)) return `${p.name} (already on this milestone)`;
    if (p.current_assignment) {
      return `${p.name} (on ${p.current_assignment.milestone_title} until ${formatDate(p.current_assignment.end_date, { withYear: false })})`;
    }
    return `${p.name} (available)`;
  };

  return (
    <Modal
      title={`Assign to ${milestone.title}`}
      description="Each person works full time (8 hours a day) on one milestone at a time."
      onClose={onClose}
    >
      <form className="form" onSubmit={form.handleSubmit} noValidate>
        <Field label="Employee" as="select" required {...form.field('user_id')}>
          <option value="">{people.loading ? 'Loading…' : 'Choose an employee'}</option>
          {(people.data || []).map((p) => (
            <option key={p.id} value={p.id}>{describe(p)}</option>
          ))}
        </Field>
        {people.data?.length === 0 && (
          <p className="field-error">{isAdmin ? 'There are no active employees yet.' : 'You have no employees on your team yet. An admin assigns them to you.'}</p>
        )}
        <div className="form-row">
          <Field label="From" type="date" min={milestone.start_date} max={milestone.end_date} required {...form.field('start_date')} />
          <Field label="To" type="date" min={milestone.start_date} max={milestone.end_date} required {...form.field('end_date')} />
        </div>
        <FormError message={form.formError} />
        <div className="modal-foot">
          <button type="button" className="button" onClick={onClose}>Cancel</button>
          <button type="submit" className="button button--primary" disabled={form.submitting}>
            {form.submitting ? 'Assigning…' : 'Assign'}
          </button>
        </div>
      </form>
    </Modal>
  );
}

AssignModal.propTypes = {
  milestone: PropTypes.shape({
    id: PropTypes.number.isRequired,
    title: PropTypes.string.isRequired,
    start_date: PropTypes.string.isRequired,
    end_date: PropTypes.string.isRequired,
    assignments: PropTypes.arrayOf(PropTypes.shape({ user_id: PropTypes.number })).isRequired,
  }).isRequired,
  isAdmin: PropTypes.bool,
  onClose: PropTypes.func.isRequired,
  onSaved: PropTypes.func.isRequired,
};

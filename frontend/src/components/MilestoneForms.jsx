import PropTypes from 'prop-types';
import Field from './Field.jsx';
import Modal from './Modal.jsx';
import { FormError } from './States.jsx';
import { useApi, useForm } from '../lib/hooks.js';
import { formatDate, todayISO } from '../lib/format.js';
import { dateOrder, first, required } from '../lib/validators.js';
import {
  createAssignment, createMilestone, listUsers, updateMilestone,
} from '../services/tracker.js';

function withinMessage(value, start, end) {
  if (value && start && value < start) return `Must be on or after ${formatDate(start)}`;
  if (value && end && value > end) return `Must be on or before ${formatDate(end)}`;
  return '';
}

/**
 * Add or edit a milestone. Dates must fall inside the project's dates.
 * Status comes from the dates and completed_at, so there's nothing to pick.
 */
export function MilestoneFormModal({
  project, milestone, onClose, onSaved,
}) {
  const editing = Boolean(milestone);
  const form = useForm(
    {
      title: milestone?.title ?? '',
      description: milestone?.description ?? '',
      start_date: milestone?.start_date ?? project.start_date,
      end_date: milestone?.end_date ?? '',
    },
    (v) => ({
      title: required(v.title),
      start_date: first(required(v.start_date), withinMessage(v.start_date, project.start_date, project.end_date)),
      end_date: first(
        required(v.end_date),
        dateOrder(v.start_date, v.end_date),
        withinMessage(v.end_date, project.start_date, project.end_date),
      ),
    }),
    async (v) => {
      const body = {
        title: v.title.trim(), description: v.description.trim() || null, start_date: v.start_date, end_date: v.end_date,
      };
      const saved = editing ? await updateMilestone(milestone.id, body) : await createMilestone(project.id, body);
      onSaved(saved);
    },
  );

  return (
    <Modal
      title={editing ? 'Edit milestone' : 'Add milestone'}
      description={`Between ${formatDate(project.start_date)} and ${formatDate(project.end_date)}. Completed milestones can't be changed.`}
      onClose={onClose}
    >
      <form className="form" onSubmit={form.handleSubmit} noValidate>
        <Field label="Title" required maxLength={150} placeholder="e.g. First 200 servers" {...form.field('title')} />
        <Field
          label="Description"
          as="textarea"
          maxLength={2000}
          hint="What has to be true for this milestone to be complete"
          {...form.field('description')}
        />
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
  }),
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

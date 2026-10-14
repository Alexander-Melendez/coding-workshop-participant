import PropTypes from 'prop-types';
import Field from './Field.jsx';
import Modal from './Modal.jsx';
import { FormError } from './States.jsx';
import { useApi, useForm } from '../lib/hooks.js';
import {
  dateOrder, first, nonNegative, required,
} from '../lib/validators.js';
import { createProject, listUsers, updateProject } from '../services/tracker.js';

/** Dropdown of active managers. */
export function ManagerSelect({ error, ...props }) {
  const managers = useApi(() => listUsers({ role: 'manager' }), []);
  return (
    <Field
      label="Manager"
      as="select"
      required
      error={error || (managers.data?.length === 0 ? 'Create a user with the manager role first' : undefined)}
      {...props}
    >
      <option value="">{managers.loading ? 'Loading…' : 'Choose a manager'}</option>
      {(managers.data || []).map((m) => <option key={m.id} value={m.id}>{`${m.name} (${m.display_id})`}</option>)}
    </Field>
  );
}

ManagerSelect.propTypes = { error: PropTypes.string };

/**
 * Create (admin) or edit (admin or the project's manager) a project.
 * Changing the budget needs a reason, which goes into the budget history.
 */
export default function ProjectFormModal({ project, onClose, onSaved }) {
  const editing = Boolean(project);
  const form = useForm(
    {
      title: project?.title ?? '',
      description: project?.description ?? '',
      start_date: project?.start_date ?? '',
      end_date: project?.end_date ?? '',
      budget: project ? String(project.budget) : '',
      estimated_hours: project ? String(project.estimated_hours ?? 0) : '',
      budget_change_reason: '',
      manager_id: '',
    },
    (v) => ({
      title: required(v.title),
      start_date: required(v.start_date),
      end_date: first(required(v.end_date), dateOrder(v.start_date, v.end_date)),
      budget: first(required(v.budget), nonNegative(v.budget)),
      estimated_hours: nonNegative(v.estimated_hours),
      manager_id: editing ? '' : required(v.manager_id),
      budget_change_reason: editing && Number(v.budget) !== Number(project.budget)
        && !v.budget_change_reason.trim() ? 'Explain why the budget is changing' : '',
    }),
    async (v) => {
      const body = {
        title: v.title.trim(),
        description: v.description.trim() || null,
        start_date: v.start_date,
        end_date: v.end_date,
        budget: Number(v.budget),
        estimated_hours: Number(v.estimated_hours || 0),
      };
      if (editing && Number(v.budget) !== Number(project.budget)) {
        body.budget_change_reason = v.budget_change_reason.trim();
      }
      const saved = editing
        ? await updateProject(project.id, body)
        : await createProject({ ...body, manager_id: Number(v.manager_id) });
      onSaved(saved);
    },
  );
  const budgetChanged = editing && Number(form.values.budget) !== Number(project.budget);

  return (
    <Modal
      title={editing ? 'Edit project' : 'New project'}
      description={editing ? undefined : 'Its manager then adds milestones and assigns their team.'}
      onClose={onClose}
      wide
    >
      <form className="form" onSubmit={form.handleSubmit} noValidate>
        <Field label="Title" required maxLength={150} {...form.field('title')} />
        <Field
          label="Description"
          as="textarea"
          maxLength={2000}
          hint="The full details: what the work is, where to find it and how to do it. Each milestone then says what counts as done."
          {...form.field('description')}
        />
        <div className="form-row">
          <Field label="Start date" type="date" required {...form.field('start_date')} />
          <Field label="End date" type="date" required {...form.field('end_date')} />
        </div>
        <div className="form-row">
          <Field label="Budget (USD)" type="number" min="0" step="1" required {...form.field('budget')} />
          <Field
            label="Estimated hours"
            type="number"
            min="0"
            step="1"
            hint="Total effort; one person-week is 40 hours"
            {...form.field('estimated_hours')}
          />
        </div>
        {budgetChanged && (
          <Field
            label="Reason for budget change"
            required
            hint="Saved in the budget history"
            maxLength={500}
            {...form.field('budget_change_reason')}
          />
        )}
        {!editing && <ManagerSelect {...form.field('manager_id')} />}
        <FormError message={form.formError} />
        <div className="modal-foot">
          <button type="button" className="button" onClick={onClose}>Cancel</button>
          <button type="submit" className="button button--primary" disabled={form.submitting}>
            {form.submitting ? 'Saving…' : (editing ? 'Save changes' : 'Create project')}
          </button>
        </div>
      </form>
    </Modal>
  );
}

ProjectFormModal.propTypes = {
  project: PropTypes.shape({
    id: PropTypes.number,
    title: PropTypes.string,
    description: PropTypes.string,
    start_date: PropTypes.string,
    end_date: PropTypes.string,
    budget: PropTypes.oneOfType([PropTypes.number, PropTypes.string]),
    estimated_hours: PropTypes.oneOfType([PropTypes.number, PropTypes.string]),
  }),
  onClose: PropTypes.func.isRequired,
  onSaved: PropTypes.func.isRequired,
};

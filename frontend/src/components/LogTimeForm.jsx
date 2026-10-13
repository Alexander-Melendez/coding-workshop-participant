import PropTypes from 'prop-types';
import Field from './Field.jsx';
import { FormError } from './States.jsx';
import { useForm } from '../lib/hooks.js';
import { formatDate, todayISO } from '../lib/format.js';
import { first, hoursInDay, required } from '../lib/validators.js';
import { createTimeEntry, updateTimeEntry } from '../services/tracker.js';

/** Group assignments by milestone so each milestone appears once. */
function milestoneOptions(assignments) {
  const map = new Map();
  assignments
    .filter((a) => !a.milestone_completed)
    .forEach((a) => {
      const existing = map.get(a.milestone_id);
      if (!existing) {
        map.set(a.milestone_id, { ...a });
      } else {
        existing.start_date = a.start_date < existing.start_date ? a.start_date : existing.start_date;
        existing.end_date = a.end_date > existing.end_date ? a.end_date : existing.end_date;
      }
    });
  return [...map.values()];
}

/**
 * Log (or edit) a day's hours on a milestone the employee is assigned to.
 * Client checks mirror the API: 0.25-8 hours, not in the future, inside
 * the assignment dates.
 */
export default function LogTimeForm({
  assignments, entry, onSaved, onCancel, submitLabel = 'Log hours',
}) {
  const options = milestoneOptions(assignments);
  const today = todayISO();
  const defaultMilestone = entry?.milestone_id
    ?? options.find((o) => o.start_date <= today && o.end_date >= today)?.milestone_id
    ?? options[0]?.milestone_id ?? '';

  const form = useForm(
    {
      milestone_id: String(defaultMilestone),
      work_date: entry?.work_date ?? today,
      hours: entry ? String(entry.hours) : '8',
      note: entry?.note ?? '',
    },
    (v) => {
      const chosen = options.find((o) => String(o.milestone_id) === String(v.milestone_id));
      let dateError = first(required(v.work_date), v.work_date > today ? "You can't log time in the future" : '');
      if (!dateError && chosen && (v.work_date < chosen.start_date || v.work_date > chosen.end_date)) {
        dateError = `You're assigned to this milestone from ${formatDate(chosen.start_date)} to ${formatDate(chosen.end_date)}`;
      }
      return {
        milestone_id: entry ? '' : required(v.milestone_id),
        work_date: dateError,
        hours: hoursInDay(v.hours),
      };
    },
    async (v) => {
      const body = { work_date: v.work_date, hours: Number(v.hours), note: v.note.trim() || null };
      const saved = entry
        ? await updateTimeEntry(entry.id, body)
        : await createTimeEntry({ ...body, milestone_id: Number(v.milestone_id) });
      onSaved(saved);
      if (!entry) form.setValues((prev) => ({ ...prev, note: '' }));
    },
  );

  if (!entry && options.length === 0) {
    return (
      <p className="muted">
        You aren&apos;t assigned to an open milestone right now. Your manager assigns you to one.
      </p>
    );
  }

  return (
    <form className="form" onSubmit={form.handleSubmit} noValidate>
      {!entry && (
        <Field label="Milestone" as="select" required {...form.field('milestone_id')}>
          {options.map((o) => (
            <option key={o.milestone_id} value={o.milestone_id}>
              {`${o.milestone_title} (${o.project_title})`}
            </option>
          ))}
        </Field>
      )}
      <div className="form-row">
        <Field label="Date" type="date" max={today} required {...form.field('work_date')} />
        <Field
          label="Hours"
          type="number"
          min="0.25"
          max="8"
          step="0.25"
          required
          hint="Up to 8 a day, 40 a week"
          {...form.field('hours')}
        />
      </div>
      <Field label="Note" as="textarea" hint="Optional: what you worked on" maxLength={500} {...form.field('note')} />
      <FormError message={form.formError} />
      <div className="actions">
        <button type="submit" className="button button--primary" disabled={form.submitting}>
          {form.submitting ? 'Saving…' : submitLabel}
        </button>
        {onCancel && <button type="button" className="button" onClick={onCancel}>Cancel</button>}
      </div>
    </form>
  );
}

LogTimeForm.propTypes = {
  assignments: PropTypes.arrayOf(PropTypes.shape({
    milestone_id: PropTypes.number.isRequired,
    milestone_title: PropTypes.string,
    project_title: PropTypes.string,
    milestone_completed: PropTypes.bool,
    start_date: PropTypes.string,
    end_date: PropTypes.string,
  })).isRequired,
  entry: PropTypes.shape({
    id: PropTypes.number,
    milestone_id: PropTypes.number,
    work_date: PropTypes.string,
    hours: PropTypes.number,
    note: PropTypes.string,
  }),
  onSaved: PropTypes.func.isRequired,
  onCancel: PropTypes.func,
  submitLabel: PropTypes.string,
};

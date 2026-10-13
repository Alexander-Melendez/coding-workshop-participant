import { useId } from 'react';
import PropTypes from 'prop-types';

/**
 * Labelled form control with hint and error text wired up for screen readers.
 * `as` picks the element: input (default), select or textarea.
 */
export default function Field({
  label, name, error, hint, required, as, children, className, ...inputProps
}) {
  const id = useId();
  const describedBy = [error ? `${id}-error` : null, hint ? `${id}-hint` : null].filter(Boolean).join(' ');
  const common = {
    id,
    name,
    'aria-invalid': error ? 'true' : undefined,
    'aria-describedby': describedBy || undefined,
    required,
    ...inputProps,
  };
  let control;
  if (as === 'select') control = <select className="select" {...common}>{children}</select>;
  else if (as === 'textarea') control = <textarea className="textarea" {...common} />;
  else control = <input className="input" {...common} />;

  return (
    <div className={`field ${className || ''}`}>
      <label htmlFor={id}>
        {label}
        {required && <span className="required" aria-hidden="true">*</span>}
      </label>
      {control}
      {hint && !error && <span id={`${id}-hint`} className="field-hint">{hint}</span>}
      {error && <span id={`${id}-error`} className="field-error">{error}</span>}
    </div>
  );
}

Field.propTypes = {
  label: PropTypes.node.isRequired,
  name: PropTypes.string.isRequired,
  error: PropTypes.string,
  hint: PropTypes.node,
  required: PropTypes.bool,
  as: PropTypes.oneOf(['input', 'select', 'textarea']),
  children: PropTypes.node,
  className: PropTypes.string,
};

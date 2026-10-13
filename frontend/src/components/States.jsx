import PropTypes from 'prop-types';

/** Shown while data loads. */
export function Loading({ label }) {
  return <div className="loading" role="status">{label || 'Loading…'}</div>;
}

Loading.propTypes = { label: PropTypes.string };

/** Error with a retry button. */
export function ErrorState({ error, onRetry }) {
  return (
    <div className="banner banner--error" role="alert">
      <strong>{error?.status === 403 ? "You don't have access to this." : "This couldn't be loaded."}</strong>
      {' '}
      {error?.message}
      {onRetry && error?.status !== 403 && (
        <>
          {' '}
          <button type="button" className="link-button" onClick={onRetry}>Try again</button>
        </>
      )}
    </div>
  );
}

ErrorState.propTypes = {
  error: PropTypes.shape({ message: PropTypes.string, status: PropTypes.number }),
  onRetry: PropTypes.func,
};

/** Nothing to show yet, with an optional next step. */
export function EmptyState({ title, children, action }) {
  return (
    <div className="empty">
      <h3>{title}</h3>
      {children && <p>{children}</p>}
      {action && <div className="actions">{action}</div>}
    </div>
  );
}

EmptyState.propTypes = {
  title: PropTypes.string.isRequired,
  children: PropTypes.node,
  action: PropTypes.node,
};

/** Form-level error from the API. */
export function FormError({ message }) {
  if (!message) return null;
  return <div className="banner banner--error" role="alert">{message}</div>;
}

FormError.propTypes = { message: PropTypes.string };

import {
  useCallback, useEffect, useRef, useState,
} from 'react';
import { ApiError } from '../services/api.js';

/**
 * Load data from an async function, tracking loading and error state.
 * Ignores responses that arrive after the inputs changed (no stale data).
 * @param {() => Promise<any>} loader
 * @param {any[]} deps re-run when these change
 */
export function useApi(loader, deps) {
  const [state, setState] = useState({ data: null, error: null, loading: true });
  const callId = useRef(0);

  // eslint-disable-next-line react-hooks/exhaustive-deps
  const load = useCallback(loader, deps);

  const reload = useCallback(async () => {
    callId.current += 1;
    const id = callId.current;
    setState((prev) => ({ ...prev, loading: true, error: null }));
    try {
      const data = await load();
      if (id === callId.current) setState({ data, error: null, loading: false });
    } catch (error) {
      if (id === callId.current) setState((prev) => ({ ...prev, error, loading: false }));
    }
  }, [load]);

  useEffect(() => {
    reload();
  }, [reload]);

  const setData = useCallback((updater) => {
    setState((prev) => ({ ...prev, data: typeof updater === 'function' ? updater(prev.data) : updater }));
  }, []);

  return { ...state, reload, setData };
}

/**
 * Form state with client validation and server field errors.
 * @param {object} initialValues
 * @param {(values: object) => object} validate returns { field: message }
 * @param {(values: object) => Promise<void>} onSubmit
 */
export function useForm(initialValues, validate, onSubmit) {
  const [values, setValues] = useState(initialValues);
  const [errors, setErrors] = useState({});
  const [formError, setFormError] = useState('');
  const [submitting, setSubmitting] = useState(false);

  const setValue = useCallback((name, value) => {
    setValues((prev) => ({ ...prev, [name]: value }));
    setErrors((prev) => (prev[name] ? { ...prev, [name]: undefined } : prev));
  }, []);

  const handleSubmit = async (event) => {
    event?.preventDefault();
    const found = validate ? validate(values) : {};
    const clean = Object.fromEntries(Object.entries(found).filter(([, v]) => v));
    setErrors(clean);
    setFormError('');
    if (Object.keys(clean).length) return;
    setSubmitting(true);
    try {
      await onSubmit(values);
    } catch (error) {
      if (error instanceof ApiError) {
        setErrors(error.fields || {});
        setFormError(error.message);
      } else {
        setFormError('Something went wrong. Please try again.');
      }
    } finally {
      setSubmitting(false);
    }
  };

  /** Props for a Field component bound to `name`. */
  const field = (name) => ({
    name,
    value: values[name] ?? '',
    error: errors[name],
    onChange: (event) => setValue(name, event.target.type === 'checkbox' ? event.target.checked : event.target.value),
  });

  return {
    values, setValue, setValues, errors, formError, submitting, handleSubmit, field,
  };
}

/** Debounce a changing value (for search boxes). */
export function useDebounced(value, delay = 300) {
  const [debounced, setDebounced] = useState(value);
  useEffect(() => {
    const timer = setTimeout(() => setDebounced(value), delay);
    return () => clearTimeout(timer);
  }, [value, delay]);
  return debounced;
}

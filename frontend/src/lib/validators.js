/**
 * Client-side validation, mirroring the API's rules so users get feedback
 * before submitting. The server still validates everything.
 */

export const required = (value) => (value === undefined || value === null || String(value).trim() === ''
  ? 'This field is required' : '');

export const email = (value) => (value && !/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(value)
  ? 'Enter a valid email address' : '');

export const username = (value) => (value && !/^[A-Za-z0-9._-]{3,40}$/.test(value)
  ? "Use 3-40 letters, numbers, '.', '-' or '_'" : '');

export const nonNegative = (value) => (value !== '' && value !== undefined && (Number.isNaN(Number(value)) || Number(value) < 0)
  ? 'Enter a number of 0 or more' : '');

export const minLength = (min) => (value) => (value && String(value).length < min
  ? `Use at least ${min} characters` : '');

/** End date must not be before start date (ISO strings compare correctly). */
export const dateOrder = (start, end) => (start && end && end < start
  ? 'Must be on or after the start date' : '');

export const hoursInDay = (value) => {
  const n = Number(value);
  if (value === '' || Number.isNaN(n)) return 'Enter the hours worked';
  if (n <= 0 || n > 8) return 'Enter between 0.25 and 8 hours';
  if (Math.round(n * 4) !== n * 4) return 'Use quarter hours (e.g. 7.5 or 7.75)';
  return '';
};

/** Run several checks and return the first message. */
export const first = (...messages) => messages.find(Boolean) || '';

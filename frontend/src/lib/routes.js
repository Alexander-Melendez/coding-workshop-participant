/**
 * Route matching for the tiny client-side router. Pure, unit tested.
 */

/**
 * Match a pattern like "/projects/:id" against a pathname.
 * @param {string} pattern route pattern with :params
 * @param {string} pathname current location pathname
 * @returns {Record<string,string>|null} params, or null if no match
 */
export function matchRoute(pattern, pathname) {
  const clean = (p) => p.replace(/\/+$/, '') || '/';
  const patternParts = clean(pattern).split('/');
  const pathParts = clean(pathname).split('/');
  if (patternParts.length !== pathParts.length) return null;
  const params = {};
  for (let i = 0; i < patternParts.length; i += 1) {
    const expected = patternParts[i];
    const actual = decodeURIComponent(pathParts[i]);
    if (expected.startsWith(':')) {
      if (!actual) return null;
      params[expected.slice(1)] = actual;
    } else if (expected !== actual) {
      return null;
    }
  }
  return params;
}

/**
 * Find the first route whose pattern matches.
 * @param {{path: string}[]} routes
 * @param {string} pathname
 */
export function resolveRoute(routes, pathname) {
  for (const route of routes) {
    const params = matchRoute(route.path, pathname);
    if (params) return { route, params };
  }
  return null;
}

/** Build a query string from an object, skipping empty values. */
export function buildQuery(params = {}) {
  const search = new URLSearchParams();
  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined && value !== null && value !== '' && value !== false) {
      search.set(key, String(value));
    }
  });
  const text = search.toString();
  return text ? `?${text}` : '';
}

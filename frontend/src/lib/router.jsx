import {
  createContext, useCallback, useContext, useEffect, useMemo, useState,
} from 'react';
import PropTypes from 'prop-types';

const RouterContext = createContext(null);

function currentLocation() {
  return { pathname: window.location.pathname, search: window.location.search };
}

/**
 * Minimal History-API router: keeps the URL in sync so refresh and the back
 * button work. CloudFront serves index.html for unknown paths (404 -> 200).
 */
export function RouterProvider({ children }) {
  const [location, setLocation] = useState(currentLocation);

  useEffect(() => {
    const onPop = () => setLocation(currentLocation());
    window.addEventListener('popstate', onPop);
    return () => window.removeEventListener('popstate', onPop);
  }, []);

  const navigate = useCallback((to, { replace = false } = {}) => {
    if (replace) window.history.replaceState(null, '', to);
    else window.history.pushState(null, '', to);
    setLocation(currentLocation());
    window.scrollTo(0, 0);
  }, []);

  const value = useMemo(() => ({
    ...location,
    query: new URLSearchParams(location.search),
    navigate,
  }), [location, navigate]);

  return <RouterContext.Provider value={value}>{children}</RouterContext.Provider>;
}

RouterProvider.propTypes = { children: PropTypes.node.isRequired };

/** Access { pathname, search, query, navigate }. */
export function useRouter() {
  const ctx = useContext(RouterContext);
  if (!ctx) throw new Error('useRouter must be used inside RouterProvider');
  return ctx;
}

/** Anchor that navigates client-side but still works with ctrl/cmd-click. */
export function Link({
  to, children, onClick, ...rest
}) {
  const { navigate } = useRouter();
  const handleClick = (event) => {
    if (onClick) onClick(event);
    if (event.defaultPrevented || event.button !== 0
      || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
    event.preventDefault();
    navigate(to);
  };
  return <a href={to} onClick={handleClick} {...rest}>{children}</a>;
}

Link.propTypes = {
  to: PropTypes.string.isRequired,
  children: PropTypes.node.isRequired,
  onClick: PropTypes.func,
};

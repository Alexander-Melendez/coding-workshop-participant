import {
  createContext, useCallback, useContext, useEffect, useMemo, useState,
} from 'react';
import PropTypes from 'prop-types';
import {
  clearTokens, configureApi, getTokens, setTokens,
} from './api.js';
import * as tracker from './tracker.js';

const AuthContext = createContext(null);

/**
 * Holds the signed-in user. Restores the session from stored tokens on load
 * and signs out automatically when the API reports the session is gone.
 */
export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [status, setStatus] = useState(getTokens() ? 'loading' : 'ready');
  const [notice, setNotice] = useState('');

  const logout = useCallback((message = '') => {
    clearTokens();
    setUser(null);
    setNotice(message);
    setStatus('ready');
  }, []);

  useEffect(() => {
    configureApi({
      onAuthLost: (message) => logout(message || 'Your session has ended. Please sign in again.'),
    });
  }, [logout]);

  useEffect(() => {
    if (!getTokens()) return;
    tracker.getMe()
      .then((me) => setUser(me))
      .catch(() => clearTokens())
      .finally(() => setStatus('ready'));
  }, []);

  const login = useCallback(async (username, password) => {
    const data = await tracker.login(username, password);
    setTokens(data);
    setNotice('');
    setUser(data.user);
    return data.user;
  }, []);

  /** The Sign out button: record it in the audit log, then forget the tokens either way. */
  const signOut = useCallback(async () => {
    try {
      await tracker.logout();
    } catch {
      // An expired session or a network error shouldn't stop someone signing out
    }
    logout();
  }, [logout]);

  const refreshUser = useCallback(async () => {
    const me = await tracker.getMe();
    setUser(me);
    return me;
  }, []);

  const value = useMemo(() => ({
    user, status, notice, login, logout, signOut, refreshUser,
  }), [user, status, notice, login, logout, signOut, refreshUser]);

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

AuthProvider.propTypes = { children: PropTypes.node.isRequired };

/** { user, status, notice, login, logout, signOut, refreshUser } */
export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used inside AuthProvider');
  return ctx;
}

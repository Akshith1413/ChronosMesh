/**
 * ChronosMesh — useAuth hook
 * Author: Guru Sai Prasad Reddy
 */

import { useState, useEffect, useCallback } from 'react';
import api from '../services/api';
import { User } from '../types';

export function useAuth() {
  const [token, setToken] = useState<string | null>(() => api.getToken());
  const [user, setUser] = useState<User | null>(() => {
    const saved = localStorage.getItem('cm_user');
    return saved ? JSON.parse(saved) : null;
  });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const handleExpired = () => {
      setToken(null);
      setUser(null);
    };
    window.addEventListener('auth:expired', handleExpired);
    window.addEventListener('auth:logout', handleExpired);
    return () => {
      window.removeEventListener('auth:expired', handleExpired);
      window.removeEventListener('auth:logout', handleExpired);
    };
  }, []);

  const login = useCallback(async (username: string, password: string) => {
    setLoading(true);
    setError(null);
    try {
      const res = await api.login(username, password);
      setToken(res.access_token);
      setUser(res.user);
      return res;
    } catch (err: any) {
      setError(err.message || 'Login failed');
      throw err;
    } finally {
      setLoading(false);
    }
  }, []);

  const logout = useCallback(() => {
    api.logout();
    setToken(null);
    setUser(null);
  }, []);

  return {
    token,
    user,
    isAuthenticated: !!token,
    loading,
    error,
    login,
    logout,
  };
}

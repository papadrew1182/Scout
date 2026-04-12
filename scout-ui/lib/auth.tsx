/**
 * Auth context: login, logout, current user, token + family persistence.
 *
 * Token is stored in localStorage (web) for persistence across refresh.
 * Active family is derived from the authenticated member, not hardcoded.
 * All API calls read the token and family from this context via api.ts setters.
 */

import { createContext, useCallback, useContext, useEffect, useState } from "react";
import { API_BASE_URL } from "./config";
import { setApiToken, setApiFamilyId, setOnUnauthorized } from "./api";

export interface AuthMember {
  member_id: string;
  family_id: string;
  first_name: string;
  last_name: string | null;
  role: "adult" | "child";
  family_name: string;
}

interface AuthState {
  token: string | null;
  member: AuthMember | null;
  loading: boolean;
  error: string | null;
  login: (email: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
}

const AuthContext = createContext<AuthState>({
  token: null,
  member: null,
  loading: true,
  error: null,
  login: async () => {},
  logout: async () => {},
});

const TOKEN_KEY = "scout_session_token";

function getStoredToken(): string | null {
  try {
    return typeof window !== "undefined" ? localStorage.getItem(TOKEN_KEY) : null;
  } catch {
    return null;
  }
}

function setStoredToken(token: string | null) {
  try {
    if (typeof window !== "undefined") {
      if (token) localStorage.setItem(TOKEN_KEY, token);
      else localStorage.removeItem(TOKEN_KEY);
    }
  } catch { /* ignore */ }
}

function syncApiState(token: string | null, member: AuthMember | null) {
  setApiToken(token);
  setApiFamilyId(member?.family_id ?? null);
}

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [token, setToken] = useState<string | null>(null);
  const [member, setMember] = useState<AuthMember | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const clearAuth = useCallback(() => {
    setToken(null);
    setMember(null);
    setStoredToken(null);
    syncApiState(null, null);
  }, []);

  // Register centralized 401 handler
  useEffect(() => {
    setOnUnauthorized(clearAuth);
  }, [clearAuth]);

  // On mount: validate stored token
  useEffect(() => {
    const stored = getStoredToken();
    if (!stored) {
      setLoading(false);
      return;
    }
    setApiToken(stored);
    fetch(`${API_BASE_URL}/api/auth/me`, {
      headers: { Authorization: `Bearer ${stored}` },
    })
      .then(async (r) => {
        if (r.ok) {
          const data = (await r.json()) as AuthMember;
          setToken(stored);
          setMember(data);
          syncApiState(stored, data);
        } else {
          clearAuth();
        }
      })
      .catch(() => clearAuth())
      .finally(() => setLoading(false));
  }, [clearAuth]);

  const login = useCallback(async (email: string, password: string) => {
    setError(null);
    const r = await fetch(`${API_BASE_URL}/api/auth/login`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, password }),
    });
    if (!r.ok) {
      setError("Invalid email or password");
      throw new Error("Login failed");
    }
    const data = await r.json();
    setToken(data.token);
    setStoredToken(data.token);
    setApiToken(data.token);

    const me = await fetch(`${API_BASE_URL}/api/auth/me`, {
      headers: { Authorization: `Bearer ${data.token}` },
    });
    if (me.ok) {
      const memberData = (await me.json()) as AuthMember;
      setMember(memberData);
      syncApiState(data.token, memberData);
    }
  }, []);

  const logout = useCallback(async () => {
    if (token) {
      await fetch(`${API_BASE_URL}/api/auth/logout`, {
        method: "POST",
        headers: { Authorization: `Bearer ${token}` },
      }).catch(() => {});
    }
    clearAuth();
  }, [token, clearAuth]);

  return (
    <AuthContext.Provider value={{ token, member, loading, error, login, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  return useContext(AuthContext);
}

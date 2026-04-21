/**
 * Auth context: login, logout, current user, token + family persistence.
 *
 * Token is stored in localStorage (web) for persistence across refresh.
 * Active family is derived from the authenticated member, not hardcoded.
 */

import { createContext, useCallback, useContext, useEffect, useState } from "react";
import { API_BASE_URL } from "./config";
import { setApiToken, setApiFamilyId, setOnUnauthorized } from "./api";
import { setSessionBearer } from "../features/lib/realClient";

export interface AuthMember {
  member_id: string;
  family_id: string;
  first_name: string;
  last_name: string | null;
  role: "adult" | "child";
  family_name: string;
  read_aloud_enabled?: boolean;
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
const FAMILY_KEY = "scout_family_id";

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
      if (token) {
        localStorage.setItem(TOKEN_KEY, token);
      } else {
        localStorage.removeItem(TOKEN_KEY);
      }
    }
  } catch {
    // ignore storage errors
  }
}

function setStoredFamilyId(familyId: string | null) {
  try {
    if (typeof window !== "undefined") {
      if (familyId) {
        localStorage.setItem(FAMILY_KEY, familyId);
      } else {
        localStorage.removeItem(FAMILY_KEY);
      }
    }
  } catch {
    // ignore storage errors
  }
}

function syncApi(t: string | null, m: AuthMember | null) {
  setApiToken(t);
  setApiFamilyId(m?.family_id ?? null);
  // Several admin forms read scout_family_id directly from localStorage
  // (/admin/home, /admin/meals/staples/new, etc.) — mirror the family
  // there so those forms can authenticate their POSTs without having
  // to round-trip through useAuth().
  setStoredFamilyId(m?.family_id ?? null);
  // Session 3 ScoutClient (realClient) reads its bearer token from a
  // module-level variable; mirror the token here so /api/me and the
  // other canonical endpoints authenticate as the logged-in actor.
  setSessionBearer(t);
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
    syncApi(null, null);
  }, []);

  useEffect(() => { setOnUnauthorized(clearAuth); }, [clearAuth]);

  useEffect(() => {
    const stored = getStoredToken();
    if (!stored) { setLoading(false); return; }
    setApiToken(stored);
    setSessionBearer(stored);
    fetch(`${API_BASE_URL}/api/auth/me`, {
      headers: { Authorization: `Bearer ${stored}` },
    })
      .then(async (r) => {
        if (r.ok) {
          const data = (await r.json()) as AuthMember;
          setToken(stored);
          setMember(data);
          syncApi(stored, data);
        } else { clearAuth(); }
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
    setSessionBearer(data.token);
    const me = await fetch(`${API_BASE_URL}/api/auth/me`, {
      headers: { Authorization: `Bearer ${data.token}` },
    });
    if (me.ok) {
      const md = (await me.json()) as AuthMember;
      setMember(md);
      syncApi(data.token, md);
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

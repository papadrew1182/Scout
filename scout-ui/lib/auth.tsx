/**
 * Auth context: login, logout, current user, token persistence.
 *
 * Token is stored in localStorage (web) for persistence across refresh.
 * All API calls read the token from this context.
 */

import { createContext, useCallback, useContext, useEffect, useState } from "react";
import { API_BASE_URL } from "./config";

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

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [token, setToken] = useState<string | null>(null);
  const [member, setMember] = useState<AuthMember | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // On mount, check for stored token and validate
  useEffect(() => {
    const stored = getStoredToken();
    if (!stored) {
      setLoading(false);
      return;
    }
    fetch(`${API_BASE_URL}/api/auth/me`, {
      headers: { Authorization: `Bearer ${stored}` },
    })
      .then(async (r) => {
        if (r.ok) {
          const data = await r.json();
          setToken(stored);
          setMember(data as AuthMember);
        } else {
          setStoredToken(null);
        }
      })
      .catch(() => {
        setStoredToken(null);
      })
      .finally(() => setLoading(false));
  }, []);

  const login = useCallback(async (email: string, password: string) => {
    setError(null);
    const r = await fetch(`${API_BASE_URL}/api/auth/login`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, password }),
    });
    if (!r.ok) {
      const text = await r.text().catch(() => "");
      setError("Invalid email or password");
      throw new Error(text || "Login failed");
    }
    const data = await r.json();
    setToken(data.token);
    setStoredToken(data.token);

    // Fetch full member info
    const me = await fetch(`${API_BASE_URL}/api/auth/me`, {
      headers: { Authorization: `Bearer ${data.token}` },
    });
    if (me.ok) {
      setMember((await me.json()) as AuthMember);
    }
  }, []);

  const logout = useCallback(async () => {
    if (token) {
      await fetch(`${API_BASE_URL}/api/auth/logout`, {
        method: "POST",
        headers: { Authorization: `Bearer ${token}` },
      }).catch(() => {});
    }
    setToken(null);
    setMember(null);
    setStoredToken(null);
  }, [token]);

  return (
    <AuthContext.Provider value={{ token, member, loading, error, login, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  return useContext(AuthContext);
}

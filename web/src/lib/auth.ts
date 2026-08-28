/**
 * Auth state and API wrappers for the registration/login service.
 *
 * Tokens are JWTs minted by the memory service (proxied through the
 * orchestrator at /api/auth/*) and stored in localStorage; every
 * authenticated request goes through `authFetch` so the bearer token
 * rides along automatically.
 */

import { config } from "../config/appConfig";

export interface AuthUser {
  id: number;
  username: string;
}

interface AuthResponse {
  token: string;
  user: AuthUser;
}

const TOKEN_KEY = "shopping_auth_token";
const USER_KEY = "shopping_auth_user";

/** Custom error carrying the HTTP status so callers can branch on it. */
export class AuthError extends Error {
  status: number;

  constructor(message: string, status: number) {
    super(message);
    this.status = status;
  }
}

export const getAuthToken = (): string | null =>
  localStorage.getItem(TOKEN_KEY);

export const getAuthUser = (): AuthUser | null => {
  try {
    const raw = localStorage.getItem(USER_KEY);
    return raw ? (JSON.parse(raw) as AuthUser) : null;
  } catch {
    return null;
  }
};

export const setAuth = (auth: AuthResponse): void => {
  localStorage.setItem(TOKEN_KEY, auth.token);
  localStorage.setItem(USER_KEY, JSON.stringify(auth.user));
};

export const clearAuth = (): void => {
  localStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem(USER_KEY);
};

/** fetch() wrapper that attaches the bearer token when logged in. */
export const authFetch = (url: string, init: RequestInit = {}): Promise<Response> => {
  const token = getAuthToken();
  const headers = new Headers(init.headers || {});
  if (token) {
    headers.set("Authorization", `Bearer ${token}`);
  }
  return fetch(url, { ...init, headers });
};

const postAuth = async (
  path: string,
  username: string,
  password: string
): Promise<AuthResponse> => {
  const response = await fetch(`${config.api.baseUrl}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ username, password }),
  });
  if (!response.ok) {
    let detail = "";
    try {
      detail = ((await response.json()) as { detail?: string }).detail || "";
    } catch {
      // Non-JSON error body; fall through with the generic message.
    }
    throw new AuthError(detail || `Auth failed: HTTP ${response.status}`, response.status);
  }
  return (await response.json()) as AuthResponse;
};

export const registerUser = async (
  username: string,
  password: string
): Promise<AuthUser> => {
  const auth = await postAuth("/auth/register", username, password);
  setAuth(auth);
  return auth.user;
};

export const loginUser = async (
  username: string,
  password: string
): Promise<AuthUser> => {
  const auth = await postAuth("/auth/login", username, password);
  setAuth(auth);
  return auth.user;
};

/** Ask the backend who the token belongs to; clears stale auth on 401. */
export const verifyAuth = async (): Promise<AuthUser | null> => {
  const token = getAuthToken();
  if (!token) return null;
  try {
    const response = await authFetch(`${config.api.baseUrl}/auth/me`);
    if (!response.ok) {
      clearAuth();
      return null;
    }
    return (await response.json()) as AuthUser;
  } catch {
    // Backend unreachable — keep the stored session optimistically.
    return getAuthUser();
  }
};

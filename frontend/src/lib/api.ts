export type ApiError = {
  status: number;
  detail: unknown;
};

const API_BASE = import.meta.env.VITE_API_URL ?? "";

let accessToken: string | null = sessionStorage.getItem("vw_access_token");
let refreshToken: string | null = sessionStorage.getItem("vw_refresh_token");

export function hasSession() {
  return Boolean(accessToken);
}

export function clearSession() {
  accessToken = null;
  refreshToken = null;
  sessionStorage.removeItem("vw_access_token");
  sessionStorage.removeItem("vw_refresh_token");
}

function saveTokens(access: string, refresh: string) {
  accessToken = access;
  refreshToken = refresh;
  sessionStorage.setItem("vw_access_token", access);
  sessionStorage.setItem("vw_refresh_token", refresh);
}

async function decodeError(response: Response): Promise<ApiError> {
  let detail: unknown = response.statusText;
  try {
    const body = await response.json();
    detail = body.detail ?? body;
  } catch {
    // Keep status text when response has no JSON body.
  }
  return { status: response.status, detail };
}

async function refreshSession(): Promise<boolean> {
  if (!refreshToken || !navigator.onLine) return false;
  const response = await fetch(`${API_BASE}/api/v1/auth/refresh`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ refresh_token: refreshToken }),
  });
  if (!response.ok) {
    clearSession();
    return false;
  }
  const body = await response.json();
  saveTokens(body.access_token, body.refresh_token);
  return true;
}

export async function api<T>(
  path: string,
  init: RequestInit = {},
  retry = true,
): Promise<T> {
  const headers = new Headers(init.headers);
  if (!headers.has("Content-Type") && init.body) {
    headers.set("Content-Type", "application/json");
  }
  if (accessToken) headers.set("Authorization", `Bearer ${accessToken}`);

  const response = await fetch(`${API_BASE}${path}`, { ...init, headers });
  if (response.status === 401 && retry && (await refreshSession())) {
    return api<T>(path, init, false);
  }
  if (!response.ok) throw await decodeError(response);
  return response.json() as Promise<T>;
}

export async function login(email: string, password: string) {
  const response = await fetch(`${API_BASE}/api/v1/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password }),
  });
  if (!response.ok) throw await decodeError(response);
  const body = await response.json();
  saveTokens(body.access_token, body.refresh_token);
  return body;
}

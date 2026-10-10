export type ApiError = {
  status: number;
  detail: unknown;
};

const API_BASE = import.meta.env.VITE_API_URL ?? "";

let accessToken: string | null = sessionStorage.getItem("mw_access_token");

export function hasSession() {
  return Boolean(accessToken);
}

export async function clearSession() {
  try {
    await fetch(`${API_BASE}/api/v1/auth/logout`, {
      method: "POST",
      credentials: "include",
    });
  } finally {
    accessToken = null;
    sessionStorage.removeItem("mw_access_token");
  }
}

function saveAccessToken(access: string) {
  accessToken = access;
  sessionStorage.setItem("mw_access_token", access);
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
  if (!navigator.onLine) return false;
  const response = await fetch(`${API_BASE}/api/v1/auth/refresh`, {
    method: "POST",
    credentials: "include",
    headers: { "Content-Type": "application/json" },
    body: "{}",
  });
  if (!response.ok) {
    accessToken = null;
    sessionStorage.removeItem("mw_access_token");
    return false;
  }
  const body = await response.json();
  saveAccessToken(body.access_token);
  return true;
}

export async function api<T>(
  path: string,
  init: RequestInit = {},
  retry = true,
): Promise<T> {
  const headers = new Headers(init.headers);
  if (
    !headers.has("Content-Type") &&
    init.body &&
    !(init.body instanceof FormData)
  ) {
    headers.set("Content-Type", "application/json");
  }
  if (accessToken) headers.set("Authorization", `Bearer ${accessToken}`);

  const response = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers,
    credentials: "include",
  });
  if (response.status === 401 && retry && (await refreshSession())) {
    return api<T>(path, init, false);
  }
  if (!response.ok) throw await decodeError(response);
  if (response.status === 204) return undefined as T;
  return response.json() as Promise<T>;
}

export async function login(email: string, password: string) {
  const response = await fetch(`${API_BASE}/api/v1/auth/login`, {
    method: "POST",
    credentials: "include",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password }),
  });
  if (!response.ok) throw await decodeError(response);
  const body = await response.json();
  saveAccessToken(body.access_token);
  return body;
}


export async function downloadApi(
  path: string,
  filename: string,
  retry = true,
): Promise<void> {
  const headers = new Headers();
  if (accessToken) headers.set("Authorization", "Bearer " + accessToken);

  const response = await fetch(API_BASE + path, {
    method: "GET",
    headers,
    credentials: "include",
  });
  if (response.status === 401 && retry && (await refreshSession())) {
    return downloadApi(path, filename, false);
  }
  if (!response.ok) throw await decodeError(response);

  const blob = await response.blob();
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  URL.revokeObjectURL(url);
}


export async function openApiDocument(path: string, retry = true): Promise<void> {
  const headers = new Headers();
  if (accessToken) headers.set("Authorization", "Bearer " + accessToken);

  const response = await fetch(API_BASE + path, {
    method: "GET",
    headers,
    credentials: "include",
  });
  if (response.status === 401 && retry && (await refreshSession())) {
    return openApiDocument(path, false);
  }
  if (!response.ok) throw await decodeError(response);

  const blob = await response.blob();
  const url = URL.createObjectURL(blob);
  const opened = window.open(url, "_blank", "noopener,noreferrer");
  if (!opened) {
    URL.revokeObjectURL(url);
    throw { status: 0, detail: "popup_blocked" } satisfies ApiError;
  }
  window.setTimeout(() => URL.revokeObjectURL(url), 60_000);
}

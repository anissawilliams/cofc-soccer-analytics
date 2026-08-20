const API = import.meta.env.VITE_API_URL || 'http://localhost:8000';
const TOKEN_KEY = 'cofc_staff_session';

function storedToken() {
  return window.sessionStorage.getItem(TOKEN_KEY) || '';
}

async function parseResponse(response, path) {
  if (!response.ok) {
    let message = `API ${response.status}: ${path}`;
    try {
      const payload = await response.json();
      if (payload?.detail) message = payload.detail;
    } catch {
      // Preserve the status-based message when the response is not JSON.
    }
    throw new Error(message);
  }
  return response.json();
}

export async function staffLogin(passcode) {
  const response = await fetch(`${API}/api/staff/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ passcode }),
    cache: 'no-store',
  });
  const payload = await parseResponse(response, '/api/staff/login');
  window.sessionStorage.setItem(TOKEN_KEY, payload.token);
  return payload;
}

export async function staffApiFetch(path) {
  const token = storedToken();
  if (!token) throw new Error('Staff sign-in required');
  const response = await fetch(`${API}${path}`, {
    headers: { Authorization: `Bearer ${token}` },
    cache: 'no-store',
  });
  if (response.status === 401) window.sessionStorage.removeItem(TOKEN_KEY);
  return parseResponse(response, path);
}

export async function verifyStaffSession() {
  if (!storedToken()) return false;
  try {
    const payload = await staffApiFetch('/api/staff/session');
    return payload.authenticated === true;
  } catch {
    return false;
  }
}

export function staffLogout() {
  window.sessionStorage.removeItem(TOKEN_KEY);
}

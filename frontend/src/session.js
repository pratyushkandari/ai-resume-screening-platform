// Single place that reads/writes the signed-in user's session.
// The token is the only credential; role/name are cached for rendering the UI.
// Authorization is always enforced by the API, never by these values.

const KEY = "session";

export function getSession() {
  try {
    const raw = localStorage.getItem(KEY);
    const session = raw ? JSON.parse(raw) : null;
    return session && session.token && session.role ? session : null;
  } catch {
    return null;
  }
}

export function saveSession({ access_token, role, name, user_id }) {
  const session = { token: access_token, role, name, userId: user_id };
  localStorage.setItem(KEY, JSON.stringify(session));
  return session;
}

export function clearSession() {
  localStorage.removeItem(KEY);
}

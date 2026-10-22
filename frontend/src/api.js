// Axios client shared by every component.
import axios from "axios";
import { clearSession, getSession } from "./session";

// Empty in Docker/dev (same-origin /api via Nginx or the Vite proxy).
// On static hosts set VITE_API_URL to the API origin, e.g. https://api.example.com
// (a bare host name is accepted and treated as https).
function normalizeBaseUrl(value) {
  const url = (value || "").trim().replace(/\/+$/, "");
  if (!url) return "";
  return /^https?:\/\//i.test(url) ? url : `https://${url}`;
}

const API_BASE_URL = normalizeBaseUrl(import.meta.env.VITE_API_URL);

const api = axios.create({
  baseURL: API_BASE_URL,
  timeout: 120000, // batch uploads embed every file before responding
  headers: { Accept: "application/json" },
});

api.interceptors.request.use((config) => {
  const session = getSession();
  if (session) config.headers.Authorization = `Bearer ${session.token}`;
  return config;
});

// An expired/invalid token ends the session; the app re-renders the login screen.
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401 && getSession()) {
      clearSession();
      window.dispatchEvent(new Event("session-expired"));
    }
    return Promise.reject(error);
  }
);

/** Human-readable message from an Axios error (FastAPI returns {"detail": string | list}). */
export function getErrorMessage(error, fallback = "Something went wrong. Please try again.") {
  const detail = error?.response?.data?.detail;
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) return detail.map((d) => d.msg || JSON.stringify(d)).join("; ");
  if (error?.code === "ECONNABORTED") return "The request timed out. Please try again.";
  if (error?.request && !error?.response) return "Cannot reach the server. Is the backend running?";
  return fallback;
}

/** Download a resume with the auth header (a plain <a href> cannot send it). */
export async function downloadResume(resumeId, fallbackName = "resume") {
  const response = await api.get(`/api/resumes/${resumeId}/download`, { responseType: "blob" });
  const disposition = response.headers["content-disposition"] || "";
  const match = /filename\*?=(?:UTF-8'')?"?([^";]+)"?/i.exec(disposition);
  const filename = match ? decodeURIComponent(match[1]) : fallbackName;
  const url = URL.createObjectURL(response.data);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

export default api;

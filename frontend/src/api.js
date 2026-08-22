// frontend/src/api.js

import axios from "axios";

// In production, empty string lets the browser call relative /api/ via Nginx reverse proxy
const BASE = import.meta.env.VITE_API_URL || "";

const api = axios.create({
  baseURL: BASE,
  timeout: 30000,
  headers: {
    Accept: "application/json",
  },
});

// Request Interceptor: Attach JWT Bearer Token to outgoing requests
api.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem("token");
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => Promise.reject(error)
);

// Response Interceptor: Handle 401 Session Expiration
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response && error.response.status === 401) {
      const currentPath = window.location.pathname;
      if (currentPath !== "/" && !currentPath.includes("login")) {
        localStorage.clear();
        window.location.href = "/";
      }
    }
    return Promise.reject(error);
  }
);

export default api;
export { BASE as API_BASE_URL };

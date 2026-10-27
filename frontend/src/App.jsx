import { lazy, Suspense, useEffect, useState } from "react";
import { Routes, Route, Navigate, useNavigate, useLocation } from "react-router-dom";
import { toast } from "react-toastify";
import Login from "./components/Login";
import { clearSession, getSession } from "./session";

// Each role downloads only its own screens (candidates never load Chart.js).
const Dashboard = lazy(() => import("./components/Dashboard"));
const UploadJob = lazy(() => import("./components/UploadJob"));
const CandidatePage = lazy(() => import("./components/CandidatePage"));
const UploadResume = lazy(() => import("./components/UploadResume"));

/**
 * Application shell: header, navigation and role-based routes.
 *
 * Without a session it renders the login screen. With one, recruiters (role
 * "hr") get the dashboard and job form; candidates get the job list and the
 * resume upload. These routes only shape the UI: the API enforces every
 * permission on its own, so editing localStorage grants nothing.
 * An expired token (any 401) fires "session-expired", which returns to login.
 */
export default function App() {
  const [session, setSession] = useState(getSession);
  const navigate = useNavigate();
  const location = useLocation();

  useEffect(() => {
    const onExpired = () => {
      setSession(null);
      toast.info("Your session has expired. Please sign in again.");
    };
    window.addEventListener("session-expired", onExpired);
    return () => window.removeEventListener("session-expired", onExpired);
  }, []);

  const handleLogin = (newSession) => {
    setSession(newSession);
    navigate("/");
  };

  const handleLogout = () => {
    clearSession();
    setSession(null);
    navigate("/");
  };

  if (!session) return <Login onLogin={handleLogin} />;

  const { role, name } = session;
  const isHR = role === "hr";

  return (
    <div style={{ minHeight: "100vh", display: "flex", flexDirection: "column", backgroundColor: "#f8fafc" }}>
      {/* Header: brand, role-based navigation, signed-in user */}
      <header className="app-header">
        <div
          onClick={() => navigate("/")}
          onKeyDown={(e) => e.key === "Enter" && navigate("/")}
          role="link"
          tabIndex={0}
          aria-label="TalentFlow home"
          className="brand-logo"
        >
          <div className="brand-icon">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
              <rect width="20" height="14" x="2" y="7" rx="2" ry="2"/>
              <path d="M16 21V5a2 2 0 0 0-2-2h-4a2 2 0 0 0-2 2v16"/>
            </svg>
          </div>
          <span className="brand-name">TalentFlow</span>
          <span className="brand-badge">ATS</span>
        </div>

        <div style={{ display: "flex", gap: "12px", alignItems: "center" }}>
          {/* HR Navigation: Dashboard & Post Job ONLY (Upload Resume is Candidate Only) */}
          {isHR ? (
            <>
              <button
                onClick={() => navigate("/")}
                className={`nav-link-btn ${location.pathname === "/" ? "active" : ""}`}
              >
                <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <rect width="7" height="9" x="3" y="3" rx="1"/>
                  <rect width="7" height="5" x="14" y="3" rx="1"/>
                  <rect width="7" height="9" x="14" y="12" rx="1"/>
                  <rect width="7" height="5" x="3" y="16" rx="1"/>
                </svg>
                Dashboard
              </button>

              <button
                onClick={() => navigate("/upload-job")}
                className={`nav-link-btn ${location.pathname === "/upload-job" ? "active" : ""}`}
              >
                <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M5 12h14"/>
                  <path d="M12 5v14"/>
                </svg>
                Post Job
              </button>
            </>
          ) : (
            /* Candidate Navigation */
            <>
              <button
                onClick={() => navigate("/")}
                className={`nav-link-btn ${location.pathname === "/" ? "active" : ""}`}
              >
                <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <circle cx="11" cy="11" r="8"/>
                  <path d="m21 21-4.3-4.3"/>
                </svg>
                Open Positions
              </button>

              <button
                onClick={() => navigate("/upload-resume")}
                className={`nav-link-btn ${location.pathname === "/upload-resume" ? "active" : ""}`}
              >
                <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>
                  <polyline points="17 8 12 3 7 8"/>
                  <line x1="12" x2="12" y1="3" y2="15"/>
                </svg>
                Submit Application
              </button>
            </>
          )}

          {/* User Profile Pill */}
          <div
            style={{
              display: "flex",
              alignItems: "center",
              gap: "8px",
              padding: "5px 10px",
              borderRadius: "6px",
              backgroundColor: "var(--slate-800)",
              border: "1px solid var(--slate-700)",
              marginLeft: "6px"
            }}
          >
            <div
              style={{
                width: 22,
                height: 22,
                borderRadius: "50%",
                backgroundColor: isHR ? "#3b82f6" : "#10b981",
                color: "#ffffff",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                fontSize: "11px",
                fontWeight: "700"
              }}
            >
              {(name || "U").charAt(0).toUpperCase()}
            </div>
            <span style={{ fontSize: "13px", fontWeight: "600", color: "#f1f5f9" }}>
              {name || "User"}
            </span>
            <span
              style={{
                fontSize: "10px",
                fontWeight: "700",
                textTransform: "uppercase",
                padding: "2px 5px",
                borderRadius: "3px",
                backgroundColor: isHR ? "rgba(59, 130, 246, 0.2)" : "rgba(16, 185, 129, 0.2)",
                color: isHR ? "#93c5fd" : "#6ee7b7",
                border: `1px solid ${isHR ? "rgba(59, 130, 246, 0.3)" : "rgba(16, 185, 129, 0.3)"}`
              }}
            >
              {role}
            </span>
          </div>

          {/* Logout Button */}
          <button
            onClick={handleLogout}
            style={{
              display: "inline-flex",
              alignItems: "center",
              gap: "5px",
              padding: "7px 12px",
              borderRadius: "6px",
              fontSize: "12px",
              fontWeight: "600",
              color: "#fca5a5",
              backgroundColor: "rgba(239, 68, 68, 0.12)",
              border: "1px solid rgba(239, 68, 68, 0.25)",
              cursor: "pointer",
              transition: "all 0.15s ease"
            }}
            onMouseOver={(e) => (e.currentTarget.style.backgroundColor = "rgba(239, 68, 68, 0.25)")}
            onMouseOut={(e) => (e.currentTarget.style.backgroundColor = "rgba(239, 68, 68, 0.12)")}
          >
            <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/>
              <polyline points="16 17 21 12 16 7"/>
              <line x1="21" x2="9" y1="12" y2="12"/>
            </svg>
            Sign Out
          </button>
        </div>
      </header>

      {/* Application Routing */}
      <main style={{ flex: 1, paddingBottom: 40 }}>
        <Suspense fallback={<div role="status" style={{ padding: 40, textAlign: "center", color: "#64748b" }}>Loading…</div>}>
        <Routes>
          {isHR ? (
            <>
              <Route path="/" element={<Dashboard />} />
              <Route path="/upload-job" element={<UploadJob />} />
              {/* HR should not access upload-resume; redirect cleanly to Dashboard */}
              <Route path="/upload-resume" element={<Navigate to="/" replace />} />
              <Route path="*" element={<Navigate to="/" replace />} />
            </>
          ) : (
            <>
              <Route path="/" element={<CandidatePage />} />
              <Route path="/candidate" element={<Navigate to="/" replace />} />
              <Route
                path="/upload-resume"
                element={
                  <div className="page" style={{ padding: "28px 32px" }}>
                    <UploadResume />
                  </div>
                }
              />
              <Route path="*" element={<Navigate to="/" replace />} />
            </>
          )}
        </Routes>
        </Suspense>
      </main>
    </div>
  );
}
import React, { useState } from "react";
import { Routes, Route, Navigate, useNavigate, useLocation } from "react-router-dom";
import Dashboard from "./components/Dashboard";
import CandidatePage from "./components/CandidatePage";
import Login from "./components/Login";
import UploadJob from "./components/UploadJob";
import UploadResume from "./components/UploadResume";

export default function App() {
  const [role, setRole] = useState(localStorage.getItem("role"));
  const navigate = useNavigate();
  const location = useLocation();

  const handleLogout = () => {
    localStorage.clear();
    setRole(null);
    navigate("/");
  };

  if (!role) return <Login setRole={setRole} />;

  return (
    <div style={{ minHeight: "100vh", display: "flex", flexDirection: "column" }}>
      {/* 🔝 Modern Top Navigation Bar */}
      <header
        style={{
          display: "flex",
          justifyContent: "space-between",
          padding: "12px 24px",
          background: "linear-gradient(90deg, #1e3a8a, #2563eb)",
          color: "#fff",
          alignItems: "center",
          boxShadow: "0 4px 16px rgba(0,0,0,0.12)",
          position: "sticky",
          top: 0,
          zIndex: 100
        }}
      >
        <div
          onClick={() => navigate(role === "hr" ? "/" : "/candidate")}
          style={{
            fontWeight: "800",
            fontSize: "20px",
            display: "flex",
            alignItems: "center",
            gap: "8px",
            cursor: "pointer",
            letterSpacing: "-0.5px"
          }}
        >
          <span>🚀</span> ResumeMatcher AI
        </div>

        <div style={{ display: "flex", gap: "10px", alignItems: "center" }}>
          {/* HR Navigation Actions */}
          {role === "hr" && (
            <>
              <button
                onClick={() => navigate("/")}
                style={{
                  background: location.pathname === "/" ? "rgba(255,255,255,0.25)" : "transparent",
                  color: "#fff",
                  border: "1px solid rgba(255,255,255,0.3)",
                  padding: "7px 12px",
                  borderRadius: "8px",
                  cursor: "pointer",
                  fontWeight: "600",
                  fontSize: "13px"
                }}
              >
                📊 Dashboard
              </button>
              <button
                onClick={() => navigate("/upload-job")}
                style={{
                  background: location.pathname === "/upload-job" ? "rgba(255,255,255,0.25)" : "transparent",
                  color: "#fff",
                  border: "1px solid rgba(255,255,255,0.3)",
                  padding: "7px 12px",
                  borderRadius: "8px",
                  cursor: "pointer",
                  fontWeight: "600",
                  fontSize: "13px"
                }}
              >
                ➕ Create Job
              </button>
              <button
                onClick={() => navigate("/upload-resume")}
                style={{
                  background: location.pathname === "/upload-resume" ? "rgba(255,255,255,0.25)" : "transparent",
                  color: "#fff",
                  border: "1px solid rgba(255,255,255,0.3)",
                  padding: "7px 12px",
                  borderRadius: "8px",
                  cursor: "pointer",
                  fontWeight: "600",
                  fontSize: "13px"
                }}
              >
                📤 Upload Resume
              </button>
            </>
          )}

          <span style={{ fontSize: "13px", opacity: 0.9, padding: "0 6px", borderLeft: "1px solid rgba(255,255,255,0.2)" }}>
            👤 {localStorage.getItem("name") || "User"} <strong style={{ textTransform: "uppercase", fontSize: "11px", background: "rgba(255,255,255,0.2)", padding: "2px 6px", borderRadius: "4px", marginLeft: "4px" }}>{role}</strong>
          </span>

          <button
            onClick={handleLogout}
            style={{
              background: "#ef4444",
              color: "#fff",
              border: "none",
              padding: "7px 14px",
              borderRadius: "8px",
              cursor: "pointer",
              fontWeight: "600",
              fontSize: "13px"
            }}
          >
            Logout
          </button>
        </div>
      </header>

      {/* 🎯 APPLICATION ROUTES */}
      <main style={{ flex: 1 }}>
        <Routes>
          {role === "hr" ? (
            <>
              <Route path="/" element={<Dashboard />} />
              <Route path="/upload-job" element={<UploadJob />} />
              <Route path="/upload-resume" element={<UploadResume />} />
              <Route path="*" element={<Navigate to="/" replace />} />
            </>
          ) : (
            <>
              <Route path="/" element={<CandidatePage />} />
              <Route path="/candidate" element={<CandidatePage />} />
              <Route path="*" element={<Navigate to="/" replace />} />
            </>
          )}
        </Routes>
      </main>
    </div>
  );
}
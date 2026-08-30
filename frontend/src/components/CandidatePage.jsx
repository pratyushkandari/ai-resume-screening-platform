import React, { useEffect, useState, useRef } from "react";
import api from "../api";
import UploadResume from "./UploadResume";

export default function CandidatePage() {
  const [jobs, setJobs] = useState([]);
  const [loading, setLoading] = useState(false);
  const [selectedJobId, setSelectedJobId] = useState("");
  const uploadSectionRef = useRef(null);

  useEffect(() => {
    loadJobs();
  }, []);

  async function loadJobs() {
    try {
      setLoading(true);
      const raw_user_id = localStorage.getItem("user_id");
      const role = (localStorage.getItem("role") || "").toLowerCase().trim();
      const user_id = Number(raw_user_id);

      const res = await api.get("/api/jobs", {
        params: {
          user_id: user_id || 0,
          role: role || "candidate"
        }
      });

      setJobs(res.data || []);
      if (res.data && res.data.length > 0) {
        setSelectedJobId(String(res.data[0].job_id));
      }
    } catch (err) {
      console.error("Failed to load jobs", err);
    } finally {
      setLoading(false);
    }
  }

  const handleApplyClick = (job_id) => {
    setSelectedJobId(String(job_id));
    if (uploadSectionRef.current) {
      uploadSectionRef.current.scrollIntoView({ behavior: "smooth" });
    }
  };

  return (
    <div style={{ padding: "28px 32px", maxWidth: 1200, margin: "0 auto" }}>
      {/* Header */}
      <div style={{ marginBottom: 28 }}>
        <h1 style={{ fontSize: 24, fontWeight: 800, color: "#0f172a", letterSpacing: "-0.02em" }}>
          Career Opportunities & Open Positions
        </h1>
        <p style={{ margin: "4px 0 0 0", color: "#64748b", fontSize: 14 }}>
          Explore open roles and submit your resume for automated competency matching and candidate evaluation.
        </p>
      </div>

      {loading ? (
        <div style={{ padding: 40, textAlign: "center", color: "#64748b" }}>
          Loading active positions...
        </div>
      ) : jobs.length === 0 ? (
        <div className="card" style={{ textAlign: "center", padding: "40px 20px" }}>
          <p style={{ color: "#64748b", fontSize: 14 }}>No active job openings available at the moment.</p>
        </div>
      ) : (
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(auto-fill, minmax(340px, 1fr))",
            gap: 18,
            marginBottom: 36
          }}
        >
          {jobs.map((j) => (
            <div
              key={j.job_id}
              className="card"
              style={{
                display: "flex",
                flexDirection: "column",
                justifyContent: "space-between",
                padding: 22
              }}
            >
              <div>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", gap: 8 }}>
                  <h3 style={{ margin: 0, fontSize: 17, fontWeight: 700, color: "#0f172a" }}>
                    {j.title}
                  </h3>
                  <span
                    style={{
                      fontSize: 11,
                      fontWeight: 700,
                      color: "#2563eb",
                      backgroundColor: "#eff6ff",
                      padding: "2px 8px",
                      borderRadius: 4,
                      border: "1px solid #dbeafe"
                    }}
                  >
                    REQ-{j.job_id}
                  </span>
                </div>

                <p style={{ fontSize: 13, color: "#475569", margin: "10px 0 14px 0", lineHeight: 1.5 }}>
                  {j.description || "No description provided."}
                </p>
              </div>

              <div>
                {j.skills && j.skills.length > 0 && (
                  <div style={{ marginBottom: 16 }}>
                    <div style={{ fontSize: 11, fontWeight: 700, color: "#64748b", textTransform: "uppercase", marginBottom: 6 }}>
                      Required Competencies:
                    </div>
                    <div style={{ display: "flex", flexWrap: "wrap", gap: 4 }}>
                      {j.skills.map((s, i) => (
                        <span
                          key={i}
                          className="chip chip-neutral"
                          style={{ fontSize: 11, padding: "2px 8px", textTransform: "capitalize" }}
                        >
                          {s}
                        </span>
                      ))}
                    </div>
                  </div>
                )}

                <button
                  onClick={() => handleApplyClick(j.job_id)}
                  className="btn btn-primary"
                  style={{ width: "100%", padding: "9px" }}
                >
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>
                    <polyline points="17 8 12 3 7 8"/>
                    <line x1="12" x2="12" y1="3" y2="15"/>
                  </svg>
                  Apply for Position
                </button>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Resume Application Submission Module */}
      <div ref={uploadSectionRef}>
        <UploadResume preselectedJobId={selectedJobId} />
      </div>
    </div>
  );
}
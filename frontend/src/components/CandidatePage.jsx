import React, { useEffect, useState } from "react";
import api from "../api";
import UploadResume from "./UploadResume";

export default function CandidatePage() {
  const [jobs, setJobs] = useState([]);
  const [loading, setLoading] = useState(false);

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
    } catch (err) {
      console.error("Failed to load jobs", err);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div style={{ padding: 24, maxWidth: 1200, margin: "0 auto" }}>
      <div style={{ marginBottom: 24 }}>
        <h1 style={{ margin: "0 0 6px 0", fontSize: 24, color: "#0f172a" }}>
          💼 Open Positions & Job Portal
        </h1>
        <p style={{ margin: 0, color: "#64748b", fontSize: 14 }}>
          Browse open job listings and upload your resume to get matched automatically by AI.
        </p>
      </div>

      {loading ? (
        <div style={{ padding: 20, textAlign: "center", color: "#64748b" }}>Loading open positions...</div>
      ) : jobs.length === 0 ? (
        <div className="card" style={{ textAlign: "center", padding: 30 }}>
          <p style={{ color: "#64748b" }}>No active job openings available at the moment.</p>
        </div>
      ) : (
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(auto-fill, minmax(320px, 1fr))",
            gap: 16,
            marginBottom: 32
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
                margin: 0
              }}
            >
              <div>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
                  <h3 style={{ margin: "0 0 6px 0", fontSize: 17, color: "#1e3a8a" }}>{j.title}</h3>
                  <span className="chip" style={{ background: "#dbeafe", color: "#1e40af", margin: 0, fontSize: 11 }}>
                    Job #{j.job_id}
                  </span>
                </div>

                <p style={{ fontSize: 13, color: "#475569", margin: "8px 0 12px 0", lineHeight: 1.5 }}>
                  {j.description || "No description provided."}
                </p>
              </div>

              {j.skills && j.skills.length > 0 && (
                <div>
                  <div style={{ fontSize: 12, fontWeight: 700, color: "#334155", marginBottom: 4 }}>
                    Required Skills:
                  </div>
                  <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
                    {j.skills.map((s, i) => (
                      <span
                        key={i}
                        className="chip matched"
                        style={{ margin: 0, fontSize: 11, padding: "3px 8px" }}
                      >
                        {s}
                      </span>
                    ))}
                  </div>
                </div>
              )}
            </div>
          ))}
        </div>
      )}

      {/* Resume Upload Module */}
      <UploadResume />
    </div>
  );
}
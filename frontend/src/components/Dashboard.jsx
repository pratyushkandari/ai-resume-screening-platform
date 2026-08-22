import React, { useEffect, useState } from "react";
import api from "../api";
import Charts from "./Charts";
import CandidateCard from "./CandidateCard";
import CandidateModal from "./CandidateModal";
import CompareModal from "./CompareModal";
import { toast } from "react-toastify";
import { useNavigate, useLocation } from "react-router-dom";

export default function Dashboard() {
  const navigate = useNavigate();
  const location = useLocation();

  const [jobs, setJobs] = useState([]);
  const [jobId, setJobId] = useState(null);
  const [summary, setSummary] = useState(null);
  const [loading, setLoading] = useState(false);
  const [compareIds, setCompareIds] = useState([]);
  const [openCandidate, setOpenCandidate] = useState(null);
  const [showCompare, setShowCompare] = useState(false);

  useEffect(() => {
    loadJobs();
  }, []);

  async function loadJobs() {
    try {
      const raw_user_id = localStorage.getItem("user_id");
      const role = localStorage.getItem("role");
      const user_id = Number(raw_user_id);

      if (!raw_user_id || !role || isNaN(user_id) || user_id <= 0) {
        toast.error("❌ Invalid session. Please log in again.");
        localStorage.clear();
        navigate("/");
        return;
      }

      const res = await api.get("/api/jobs", {
        params: { user_id, role }
      });

      const jobList = res.data || [];
      setJobs(jobList);

      // Check if a specific jobId was passed in via navigation state
      const targetJobId = location.state?.selectedJobId;
      if (targetJobId && jobList.some((j) => j.job_id === targetJobId)) {
        setJobId(targetJobId);
        fetchSummary(targetJobId);
      } else if (jobList.length > 0 && !jobId) {
        setJobId(jobList[0].job_id);
        fetchSummary(jobList[0].job_id);
      }
    } catch (e) {
      toast.error("❌ Failed to fetch jobs list");
    }
  }

  async function fetchSummary(id) {
    if (!id) {
      setSummary(null);
      return;
    }

    setLoading(true);
    try {
      const raw_user_id = localStorage.getItem("user_id");
      const role = localStorage.getItem("role");
      const user_id = Number(raw_user_id);

      if (!raw_user_id || !role || isNaN(user_id) || user_id <= 0) {
        toast.error("❌ Session expired. Please login again.");
        localStorage.clear();
        navigate("/");
        return;
      }

      const res = await api.get(`/api/jobs/${Number(id)}/summary`, {
        params: { user_id, role }
      });

      setSummary(res.data || null);
    } catch (e) {
      const errorMsg = e.response?.data?.detail || "Failed to load job analytics";
      toast.error(`❌ ${errorMsg}`);
      setSummary(null);
    } finally {
      setLoading(false);
    }
  }

  async function generateRankings() {
    if (!jobId) {
      toast.warn("⚠️ Please select a job opening first");
      return;
    }
    setLoading(true);
    try {
      const res = await api.post(`/api/jobs/${Number(jobId)}/rank`);
      toast.success(`✅ Generated rankings for ${res.data?.ranked || 0} candidate resumes!`);
      await fetchSummary(jobId);
    } catch (e) {
      toast.error("❌ Ranking generation failed");
    } finally {
      setLoading(false);
    }
  }

  function onJobSelect(e) {
    const val = e.target.value;
    const numeric = val ? Number(val) : null;
    setJobId(numeric);
    setCompareIds([]); // Clear selection when switching jobs to prevent cross-job comparison errors
    fetchSummary(numeric);
  }

  function toggleCompare(candidate_id) {
    setCompareIds((prev) => {
      if (prev.includes(candidate_id)) {
        return prev.filter((x) => x !== candidate_id);
      } else {
        return [...prev, candidate_id];
      }
    });
  }

  return (
    <div style={{ padding: 24, maxWidth: 1280, margin: "0 auto" }}>
      {/* 🧭 HEADER & ACTIONS BAR */}
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          flexWrap: "wrap",
          gap: 16,
          marginBottom: 20
        }}
      >
        <div>
          <h1 style={{ margin: "0 0 4px 0", fontSize: 22, color: "#0f172a", fontWeight: "800" }}>
            🤖 AI Resume Matching & Ranking Dashboard
          </h1>
          <p style={{ margin: 0, color: "#64748b", fontSize: 14 }}>
            Rank applicants using semantic embeddings, skill-gap vectors, and automated shortlisting.
          </p>
        </div>

        <div style={{ display: "flex", gap: 10, alignItems: "center", flexWrap: "wrap" }}>
          <select
            value={jobId ?? ""}
            onChange={onJobSelect}
            style={{
              padding: "10px 14px",
              borderRadius: 8,
              border: "1px solid #cbd5e1",
              minWidth: 260,
              fontWeight: 600,
              fontSize: 14,
              background: "#fff"
            }}
          >
            <option value="">-- Select a Job Opening --</option>
            {jobs.map((j) => (
              <option key={j.job_id} value={j.job_id}>
                #{j.job_id} — {j.title}
              </option>
            ))}
          </select>

          <button
            onClick={generateRankings}
            disabled={!jobId || loading}
            className="btn"
            style={{ padding: "10px 16px" }}
          >
            {loading ? "Processing..." : "⚡ Generate Rankings"}
          </button>

          <button
            onClick={() => navigate("/upload-job")}
            style={{
              padding: "10px 16px",
              borderRadius: 8,
              border: "none",
              background: "#16a34a",
              color: "#fff",
              cursor: "pointer",
              fontWeight: "700",
              fontSize: "14px"
            }}
          >
            ➕ New Job
          </button>
        </div>
      </div>

      {!summary ? (
        <div
          style={{
            marginTop: 24,
            borderRadius: 16,
            padding: 40,
            textAlign: "center",
            background: "linear-gradient(135deg, #f8fafc, #eef2ff)",
            border: "1px solid #e2e8f0",
            boxShadow: "0 10px 25px rgba(0,0,0,0.04)"
          }}
        >
          <div style={{ fontSize: 48 }}>📊</div>
          <h2 style={{ margin: "12px 0 6px 0", color: "#1e293b" }}>No Job Selected</h2>
          <p style={{ color: "#64748b", fontSize: 14, maxWidth: 500, margin: "0 auto" }}>
            Select an active job opening from the dropdown above to view candidate rankings, skill coverage, and semantic matching charts.
          </p>
        </div>
      ) : (
        <>
          {/* 📊 OVERVIEW & CHARTS */}
          <div className="card" style={{ marginTop: 16 }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 16 }}>
              <div>
                <h2 style={{ margin: 0, fontSize: 18, color: "#0f172a" }}>
                  📋 {summary.title}
                </h2>
                <div className="small" style={{ marginTop: 2 }}>
                  Job ID: <strong>#{summary.job_id}</strong> • <strong>{summary.job_skills?.length || 0}</strong> Required Skills • <strong>{summary.candidates?.length || 0}</strong> Evaluated Candidates
                </div>
              </div>

              <div>
                <div className="small" style={{ fontWeight: 600, marginBottom: 4 }}>Required Skills:</div>
                <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
                  {(summary.job_skills || []).map((s) => (
                    <span key={s} className="chip matched" style={{ margin: 0 }}>
                      {s}
                    </span>
                  ))}
                </div>
              </div>
            </div>

            <Charts
              jobSkillCounts={summary.job_skill_counts || []}
              candidates={summary.candidates || []}
            />
          </div>

          {/* 👥 RANKED CANDIDATES LIST */}
          <div className="card" style={{ marginTop: 16 }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 16 }}>
              <div className="card-title" style={{ margin: 0 }}>
                🏆 Ranked Candidates ({summary.candidates?.length || 0})
              </div>
              <div className="small">
                Sorted by AI Composite Score (Semantic Similarity + Skill Overlap)
              </div>
            </div>

            {summary.candidates?.length === 0 ? (
              <div style={{ textAlign: "center", padding: 30, color: "#64748b" }}>
                No candidate resumes have been submitted for this job opening yet.
                <div style={{ marginTop: 12 }}>
                  <button
                    onClick={() => navigate(`/upload-resume?jobId=${jobId}`)}
                    className="btn"
                  >
                    📤 Upload Resumes Now
                  </button>
                </div>
              </div>
            ) : (
              <div className="card-grid">
                {(summary.candidates || []).map((c) => (
                  <CandidateCard
                    key={`${c.resume_id}-${c.candidate_id}`}
                    candidate={c}
                    isSelected={compareIds.includes(c.candidate_id)}
                    onViewRadar={(cand) => setOpenCandidate(cand)}
                    onToggleCompare={(candId) => toggleCompare(candId)}
                  />
                ))}
              </div>
            )}
          </div>
        </>
      )}

      {/* Candidate Radar Modal */}
      {openCandidate && (
        <CandidateModal
          candidate={openCandidate}
          jobSkills={summary?.job_skills || []}
          onClose={() => setOpenCandidate(null)}
        />
      )}

      {/* Side-by-Side Comparison Modal */}
      {showCompare && (
        <CompareModal
          ids={compareIds}
          jobId={jobId}
          onClose={() => {
            setShowCompare(false);
            setCompareIds([]);
          }}
        />
      )}

      {/* Floating Bottom Action Drawer for Comparison */}
      {compareIds.length > 0 && (
        <div
          style={{
            position: "fixed",
            bottom: 24,
            left: "50%",
            transform: "translateX(-50%)",
            background: "#0f172a",
            color: "#fff",
            padding: "12px 24px",
            borderRadius: 14,
            boxShadow: "0 14px 35px rgba(0,0,0,0.3)",
            display: "flex",
            gap: 16,
            alignItems: "center",
            zIndex: 1000
          }}
        >
          <span style={{ fontWeight: 600, fontSize: 14 }}>
            🎯 <strong>{compareIds.length}</strong> candidates selected for comparison
          </span>

          <button
            onClick={() => setShowCompare(true)}
            disabled={compareIds.length < 2}
            style={{
              padding: "8px 16px",
              borderRadius: 8,
              border: "none",
              background: compareIds.length < 2 ? "#64748b" : "#22c55e",
              color: "#fff",
              cursor: compareIds.length < 2 ? "not-allowed" : "pointer",
              fontWeight: "700",
              fontSize: 13
            }}
          >
            Launch Side-by-Side Comparison
          </button>

          <button
            onClick={() => setCompareIds([])}
            style={{
              padding: "8px 12px",
              borderRadius: 8,
              border: "none",
              background: "rgba(255,255,255,0.15)",
              color: "#fff",
              cursor: "pointer",
              fontSize: 13
            }}
          >
            Clear Selection
          </button>
        </div>
      )}
    </div>
  );
}
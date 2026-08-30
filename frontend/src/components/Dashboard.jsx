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
        toast.error("Invalid session. Please log in again.");
        localStorage.clear();
        navigate("/");
        return;
      }

      const res = await api.get("/api/jobs", {
        params: { user_id, role }
      });

      const jobList = res.data || [];
      setJobs(jobList);

      const targetJobId = location.state?.selectedJobId;
      if (targetJobId && jobList.some((j) => j.job_id === targetJobId)) {
        setJobId(targetJobId);
        fetchSummary(targetJobId);
      } else if (jobList.length > 0 && !jobId) {
        setJobId(jobList[0].job_id);
        fetchSummary(jobList[0].job_id);
      }
    } catch (e) {
      toast.error("Failed to retrieve requisition list.");
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
        toast.error("Session expired. Please sign in again.");
        localStorage.clear();
        navigate("/");
        return;
      }

      const res = await api.get(`/api/jobs/${Number(id)}/summary`, {
        params: { user_id, role }
      });

      setSummary(res.data || null);
    } catch (e) {
      const errorMsg = e.response?.data?.detail || "Failed to load candidate analytics";
      toast.error(errorMsg);
      setSummary(null);
    } finally {
      setLoading(false);
    }
  }

  async function generateRankings() {
    if (!jobId) {
      toast.warn("Please select an active job requisition first");
      return;
    }
    setLoading(true);
    try {
      const res = await api.post(`/api/jobs/${Number(jobId)}/rank`);
      toast.success(`Evaluated and ranked ${res.data?.ranked || 0} candidate profiles.`);
      await fetchSummary(jobId);
    } catch (e) {
      toast.error("Candidate evaluation pipeline encountered an error.");
    } finally {
      setLoading(false);
    }
  }

  function onJobSelect(e) {
    const val = e.target.value;
    const numeric = val ? Number(val) : null;
    setJobId(numeric);
    setCompareIds([]);
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

  // Calculate high-level summary metrics
  const totalApplicants = summary?.candidates?.length || 0;
  const shortlistedCount = (summary?.candidates || []).filter(c => c.status === "accepted").length;
  const avgScore = totalApplicants > 0
    ? Math.round(((summary.candidates.reduce((acc, c) => acc + (c.score || 0), 0) / totalApplicants) * 100))
    : 0;

  return (
    <div style={{ padding: "28px 32px", maxWidth: 1320, margin: "0 auto" }}>
      {/* Recruiter Header & Job Action Bar */}
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          flexWrap: "wrap",
          gap: 16,
          marginBottom: 24
        }}
      >
        <div>
          <h1 style={{ fontSize: 24, fontWeight: 800, color: "#0f172a", letterSpacing: "-0.02em" }}>
            Candidate Evaluation & Rankings
          </h1>
          <p style={{ margin: "4px 0 0 0", color: "#64748b", fontSize: 14 }}>
            Review applicant profiles, technical skill overlap, and semantic matching for open requisitions.
          </p>
        </div>

        <div style={{ display: "flex", gap: 10, alignItems: "center", flexWrap: "wrap" }}>
          {/* Position Selector Dropdown */}
          <div style={{ position: "relative" }}>
            <select
              value={jobId ?? ""}
              onChange={onJobSelect}
              style={{
                padding: "9px 36px 9px 14px",
                borderRadius: 8,
                border: "1px solid #cbd5e1",
                minWidth: 280,
                fontWeight: 600,
                fontSize: 13,
                backgroundColor: "#ffffff",
                color: "#0f172a",
                cursor: "pointer",
                appearance: "none"
              }}
            >
              <option value="">-- Select Active Position --</option>
              {jobs.map((j) => (
                <option key={j.job_id} value={j.job_id}>
                  REQ-{j.job_id}: {j.title}
                </option>
              ))}
            </select>
            <svg
              width="14"
              height="14"
              viewBox="0 0 24 24"
              fill="none"
              stroke="#64748b"
              strokeWidth="2"
              style={{ position: "absolute", right: 12, top: "50%", transform: "translateY(-50%)", pointerEvents: "none" }}
            >
              <polyline points="6 9 12 15 18 9" />
            </svg>
          </div>

          <button
            onClick={generateRankings}
            disabled={!jobId || loading}
            className="btn btn-primary"
            style={{ padding: "9px 16px", fontSize: 13 }}
          >
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M21.5 2v6h-6M21.34 15.57a10 10 0 1 1-.57-8.38l5.67-5.67"/>
            </svg>
            {loading ? "Evaluating..." : "Evaluate Candidates"}
          </button>

          <button
            onClick={() => navigate("/upload-job")}
            className="btn btn-secondary"
            style={{ padding: "9px 16px", fontSize: 13 }}
          >
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M5 12h14"/>
              <path d="M12 5v14"/>
            </svg>
            Post Position
          </button>
        </div>
      </div>

      {/* Recruiter Analytics Metrics Strip */}
      <div className="stats-grid">
        <div className="stat-box">
          <div className="stat-label">Active Requisitions</div>
          <div className="stat-value">{jobs.length}</div>
          <div className="stat-desc">Published open positions</div>
        </div>

        <div className="stat-box">
          <div className="stat-label">Total Applicants</div>
          <div className="stat-value">{totalApplicants}</div>
          <div className="stat-desc">For selected requisition</div>
        </div>

        <div className="stat-box">
          <div className="stat-label">Shortlisted Candidates</div>
          <div className="stat-value" style={{ color: "#059669" }}>{shortlistedCount}</div>
          <div className="stat-desc">Exceeding qualification threshold</div>
        </div>

        <div className="stat-box">
          <div className="stat-label">Average Match Score</div>
          <div className="stat-value" style={{ color: "#2563eb" }}>{avgScore}%</div>
          <div className="stat-desc">Composite semantic & skill fit</div>
        </div>
      </div>

      {!summary ? (
        /* Clean Empty State */
        <div
          style={{
            marginTop: 20,
            borderRadius: 12,
            padding: "48px 24px",
            textAlign: "center",
            backgroundColor: "#ffffff",
            border: "1px solid #e2e8f0",
            boxShadow: "0 1px 3px rgba(0,0,0,0.05)"
          }}
        >
          <div
            style={{
              width: 48,
              height: 48,
              borderRadius: "50%",
              backgroundColor: "#f1f5f9",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              margin: "0 auto 16px auto",
              color: "#64748b"
            }}
          >
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <circle cx="11" cy="11" r="8"/>
              <path d="m21 21-4.3-4.3"/>
            </svg>
          </div>
          <h2 style={{ fontSize: 18, fontWeight: 700, color: "#1e293b", marginBottom: 6 }}>No Position Selected</h2>
          <p style={{ color: "#64748b", fontSize: 14, maxWidth: 460, margin: "0 auto 18px auto" }}>
            Select an active job requisition from the dropdown above to review candidate rankings, skill gap metrics, and semantic match distributions.
          </p>
          {jobs.length === 0 && (
            <button onClick={() => navigate("/upload-job")} className="btn btn-primary">
              Create Your First Position
            </button>
          )}
        </div>
      ) : (
        <>
          {/* Position Overview & Skill Fit Analytics */}
          <div className="card" style={{ marginBottom: 20 }}>
            <div
              style={{
                display: "flex",
                justifyContent: "space-between",
                alignItems: "flex-start",
                flexWrap: "wrap",
                gap: 16,
                paddingBottom: 16,
                borderBottom: "1px solid #f1f5f9",
                marginBottom: 20
              }}
            >
              <div>
                <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
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
                    REQ-{summary.job_id}
                  </span>
                  <h2 style={{ margin: 0, fontSize: 18, fontWeight: 700, color: "#0f172a" }}>
                    {summary.title}
                  </h2>
                </div>
                <div style={{ fontSize: 13, color: "#64748b", marginTop: 4 }}>
                  <span>{summary.job_skills?.length || 0} Required Skills</span>
                  <span style={{ margin: "0 6px" }}>•</span>
                  <span>{summary.candidates?.length || 0} Candidates Evaluated</span>
                </div>
              </div>

              <div>
                <div style={{ fontSize: 12, fontWeight: 600, color: "#475569", marginBottom: 6 }}>
                  Target Competencies:
                </div>
                <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
                  {(summary.job_skills || []).map((s) => (
                    <span key={s} className="chip chip-neutral" style={{ textTransform: "capitalize" }}>
                      {s}
                    </span>
                  ))}
                </div>
              </div>
            </div>

            {/* Visual Analytics Charts */}
            <Charts
              jobSkillCounts={summary.job_skill_counts || []}
              candidates={summary.candidates || []}
            />
          </div>

          {/* Candidate Applications Pipeline */}
          <div className="card">
            <div
              style={{
                display: "flex",
                justifyContent: "space-between",
                alignItems: "center",
                marginBottom: 18,
                flexWrap: "wrap",
                gap: 12
              }}
            >
              <div>
                <div className="card-title">Applicant Pool ({summary.candidates?.length || 0})</div>
                <div className="card-subtitle">
                  Ranked by composite scoring (Dense Semantic Similarity + Skill Overlap)
                </div>
              </div>

              {summary.candidates?.length > 0 && (
                <div style={{ fontSize: 12, color: "#64748b", fontWeight: 500 }}>
                  Showing all evaluated applicants for this position
                </div>
              )}
            </div>

            {summary.candidates?.length === 0 ? (
              <div
                style={{
                  textAlign: "center",
                  padding: "40px 20px",
                  color: "#64748b",
                  backgroundColor: "#f8fafc",
                  borderRadius: 8,
                  border: "1px dashed #cbd5e1"
                }}
              >
                <div style={{ fontWeight: 600, color: "#334155", fontSize: 14, marginBottom: 4 }}>
                  No candidate applications received yet
                </div>
                <div style={{ fontSize: 13, color: "#64748b" }}>
                  As candidates apply through the Career Portal, their profiles and automated rankings will appear here in real time.
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

      {/* Candidate Profile Breakdown Modal */}
      {openCandidate && (
        <CandidateModal
          candidate={openCandidate}
          jobSkills={summary?.job_skills || []}
          onClose={() => setOpenCandidate(null)}
        />
      )}

      {/* Candidate Comparison Modal */}
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

      {/* Floating Bottom Comparison Drawer */}
      {compareIds.length > 0 && (
        <div
          style={{
            position: "fixed",
            bottom: 24,
            left: "50%",
            transform: "translateX(-50%)",
            backgroundColor: "#0f172a",
            color: "#ffffff",
            padding: "12px 20px",
            borderRadius: 12,
            boxShadow: "0 10px 25px -5px rgba(0,0,0,0.4)",
            display: "flex",
            alignItems: "center",
            gap: 16,
            zIndex: 100,
            border: "1px solid #334155"
          }}
        >
          <div style={{ fontSize: 13, fontWeight: 600 }}>
            {compareIds.length} candidate{compareIds.length > 1 ? "s" : ""} selected for comparison
          </div>

          <div style={{ display: "flex", gap: 8 }}>
            <button
              onClick={() => setShowCompare(true)}
              className="btn btn-primary"
              style={{ fontSize: 12, padding: "6px 14px" }}
            >
              Compare Profiles
            </button>
            <button
              onClick={() => setCompareIds([])}
              className="btn btn-ghost"
              style={{ fontSize: 12, padding: "6px 10px", color: "#94a3b8" }}
            >
              Clear
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
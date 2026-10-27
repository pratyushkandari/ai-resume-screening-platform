import { useCallback, useEffect, useRef, useState } from "react";
import api, { getErrorMessage } from "../api";
import Charts from "./Charts";
import CandidateCard from "./CandidateCard";
import CandidateModal from "./CandidateModal";
import CompareModal from "./CompareModal";
import { toast } from "react-toastify";
import { useNavigate, useLocation } from "react-router-dom";

/**
 * Recruiter dashboard for one of the recruiter's own jobs.
 *
 * Data flow: GET /api/jobs/mine fills the job selector; GET /api/jobs/{id}/summary
 * returns scores, skills and chart data for the selected job; "Evaluate Candidates"
 * calls POST /api/jobs/{id}/rank (fills missing embeddings, saves a snapshot) and
 * then reloads the summary. A job id passed in router state (after posting a job)
 * is selected first. Comparison selections are keyed by `resume_id`, the one id
 * every summary entry is guaranteed to have.
 */
export default function Dashboard() {
  const navigate = useNavigate();
  const location = useLocation();

  const [jobs, setJobs] = useState([]);
  const [jobsStatus, setJobsStatus] = useState("loading"); // loading | error | ready
  const [jobsAttempt, setJobsAttempt] = useState(0); // incremented to retry loading the jobs
  const [jobId, setJobId] = useState(null);
  const [summary, setSummary] = useState(null);
  const [summaryStatus, setSummaryStatus] = useState("idle"); // idle | loading | error | ready
  const [ranking, setRanking] = useState(false);
  const [compareIds, setCompareIds] = useState([]);
  const [openCandidate, setOpenCandidate] = useState(null);
  const [showCompare, setShowCompare] = useState(false);

  // Only the most recent request may update the screen: when the recruiter switches
  // jobs quickly, a slower response for the previous job must not overwrite the new one.
  const latestRequest = useRef(0);
  const selectedJob = useRef(null);
  useEffect(() => {
    selectedJob.current = jobId;
  }, [jobId]);

  const fetchSummary = useCallback(async (id) => {
    const requestId = ++latestRequest.current;
    if (!id) {
      setSummary(null);
      setSummaryStatus("idle");
      return;
    }
    setSummaryStatus("loading");
    try {
      const res = await api.get(`/api/jobs/${Number(id)}/summary`);
      if (requestId === latestRequest.current) {
        setSummary(res.data || null);
        setSummaryStatus("ready");
      }
    } catch (err) {
      if (requestId === latestRequest.current) {
        toast.error(getErrorMessage(err, "Failed to load candidate analytics."));
        setSummary(null);
        setSummaryStatus("error");
      }
    }
  }, []);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const res = await api.get("/api/jobs/mine");
        if (cancelled) return;
        const jobList = res.data || [];
        setJobs(jobList);
        setJobsStatus("ready");
        const requested = location.state?.selectedJobId;
        const initial = jobList.some((j) => j.job_id === requested) ? requested : jobList[0]?.job_id;
        if (initial) {
          setJobId(initial);
          fetchSummary(initial);
        }
      } catch (err) {
        if (!cancelled) {
          toast.error(getErrorMessage(err, "Failed to load your job requisitions."));
          setJobsStatus("error");
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [fetchSummary, location.state, jobsAttempt]);

  function retryJobs() {
    setJobsStatus("loading");
    setJobsAttempt((n) => n + 1);
  }

  async function generateRankings() {
    if (!jobId) {
      toast.warn("Please select a job requisition first.");
      return;
    }
    const rankedJob = jobId;
    // Stays set even if the recruiter switches jobs meanwhile, so the same
    // evaluation cannot be started twice.
    setRanking(true);
    try {
      const res = await api.post(`/api/jobs/${Number(rankedJob)}/rank`);
      toast.success(`Re-evaluated ${res.data?.ranked || 0} resumes and saved the rankings.`);
      // Refresh only if the recruiter is still looking at the job that was ranked.
      if (selectedJob.current === rankedJob) await fetchSummary(rankedJob);
    } catch (err) {
      toast.error(getErrorMessage(err, "Candidate evaluation failed."));
    } finally {
      setRanking(false);
    }
  }

  function onJobSelect(e) {
    const val = e.target.value;
    const numeric = val ? Number(val) : null;
    setJobId(numeric);
    setCompareIds([]);
    setSummary(null); // never show the previous job's candidates under the new selection
    fetchSummary(numeric);
  }

  function toggleCompare(resumeId) {
    setCompareIds((prev) => (prev.includes(resumeId) ? prev.filter((x) => x !== resumeId) : [...prev, resumeId]));
  }

  // Calculate high-level summary metrics
  const totalApplicants = summary?.candidates?.length || 0;
  const shortlistedCount = (summary?.candidates || []).filter(c => c.status === "accepted").length;
  const avgScore = totalApplicants > 0
    ? Math.round(((summary.candidates.reduce((acc, c) => acc + (c.score || 0), 0) / totalApplicants) * 100))
    : 0;

  // What to show instead of the analytics while there is no summary to display.
  let placeholder = null;
  if (jobsStatus === "loading") {
    placeholder = { title: "Loading your positions…", busy: true };
  } else if (jobsStatus === "error") {
    placeholder = {
      title: "Couldn't load your positions",
      text: "Check that the server is reachable, then try again.",
      action: { label: "Try Again", onClick: retryJobs },
    };
  } else if (jobs.length === 0) {
    placeholder = {
      title: "No Positions Yet",
      text: "Post your first position to start receiving applications and ranking candidates.",
      action: { label: "Create Your First Position", onClick: () => navigate("/upload-job") },
    };
  } else if (!jobId) {
    placeholder = {
      title: "No Position Selected",
      text: "Select an active job requisition from the dropdown above to review candidate rankings, skill gap metrics, and semantic match distributions.",
    };
  } else if (summaryStatus === "error") {
    placeholder = {
      title: "Couldn't load candidate analytics",
      text: "Check that the server is reachable, then try again.",
      action: { label: "Try Again", onClick: () => fetchSummary(jobId) },
    };
  } else if (!summary) {
    placeholder = { title: "Loading candidate analytics…", busy: true };
  }

  return (
    <div className="page" style={{ padding: "28px 32px", maxWidth: 1320, margin: "0 auto" }}>
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
              aria-label="Select job requisition"
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
              <option value="">-- Select one of your positions --</option>
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
            disabled={!jobId || ranking}
            className="btn btn-primary"
            style={{ padding: "9px 16px", fontSize: 13 }}
          >
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M21.5 2v6h-6M21.34 15.57a10 10 0 1 1-.57-8.38l5.67-5.67"/>
            </svg>
            {ranking ? "Evaluating..." : "Evaluate Candidates"}
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

      {placeholder ? (
        /* Loading, error and empty states */
        <div
          role="status"
          aria-busy={placeholder.busy || undefined}
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
          <h2 style={{ fontSize: 18, fontWeight: 700, color: "#1e293b", marginBottom: 6 }}>{placeholder.title}</h2>
          {placeholder.text && (
            <p style={{ color: "#64748b", fontSize: 14, maxWidth: 460, margin: "0 auto 18px auto" }}>
              {placeholder.text}
            </p>
          )}
          {placeholder.action && (
            <button onClick={placeholder.action.onClick} className="btn btn-primary">
              {placeholder.action.label}
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
                  <span style={{ margin: "0 6px" }}>•</span>
                  <span>
                    {summary.last_ranked_at
                      ? `Rankings saved ${new Date(summary.last_ranked_at).toLocaleString()}`
                      : "Rankings not saved yet"}
                  </span>
                </div>
                {!summary.semantic_available && summary.candidates?.length > 0 && (
                  <div role="note" style={{ fontSize: 12, color: "#b45309", marginTop: 6 }}>
                    Some semantic scores are neutral (50%) because the embedding model was unavailable.
                    Use “Evaluate Candidates” once the model is loaded to fill them in.
                  </div>
                )}
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
                    key={c.resume_id}
                    candidate={c}
                    isSelected={compareIds.includes(c.resume_id)}
                    onViewRadar={(cand) => setOpenCandidate(cand)}
                    onToggleCompare={toggleCompare}
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
          candidates={(summary?.candidates || []).filter((c) => compareIds.includes(c.resume_id))}
          jobSkills={summary?.job_skills || []}
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
            // Centred with auto margins between 16px gutters, so on phones the bar can
            // use the full width (centring with left: 50% would cap it at half the screen).
            left: 16,
            right: 16,
            margin: "0 auto",
            width: "fit-content",
            backgroundColor: "#0f172a",
            color: "#ffffff",
            padding: "12px 20px",
            borderRadius: 12,
            boxShadow: "0 10px 25px -5px rgba(0,0,0,0.4)",
            display: "flex",
            flexWrap: "wrap",
            justifyContent: "center",
            alignItems: "center",
            gap: "10px 16px",
            zIndex: 100,
            border: "1px solid #334155"
          }}
        >
          <div style={{ fontSize: 13, fontWeight: 600 }}>
            {compareIds.length < 2
              ? "Select one more candidate to compare"
              : `${compareIds.length} candidates selected for comparison`}
          </div>

          <div style={{ display: "flex", gap: 8 }}>
            <button
              onClick={() => setShowCompare(true)}
              disabled={compareIds.length < 2}
              title={compareIds.length < 2 ? "Select at least two candidates" : undefined}
              className="btn btn-primary"
              style={{ fontSize: 12, padding: "6px 14px" }}
            >
              Compare Profiles
            </button>
            <button
              onClick={() => setCompareIds([])}
              className="btn btn-ghost-dark"
              style={{ fontSize: 12, padding: "6px 10px" }}
            >
              Clear
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
import React, { useEffect, useState, useMemo } from "react";
import api from "../api";
import { Radar, Bar } from "react-chartjs-2";
import {
  Chart as ChartJS,
  RadialLinearScale,
  PointElement,
  LineElement,
  Filler,
  Tooltip,
  Legend,
  CategoryScale,
  LinearScale,
  BarElement,
} from "chart.js";
import "./CompareModal.css";

ChartJS.register(
  RadialLinearScale,
  PointElement,
  LineElement,
  Filler,
  Tooltip,
  Legend,
  CategoryScale,
  LinearScale,
  BarElement
);

const PALETTE = [
  "#2563eb", "#059669", "#db2777", "#d97706",
  "#8b5cf6", "#e11d48", "#0ea5a6", "#1f2937",
  "#065f46", "#be185d"
];

function hexToRGBA(hex, alpha = 1) {
  const h = hex.replace("#", "");
  const r = parseInt(h.substring(0, 2), 16) || 37;
  const g = parseInt(h.substring(2, 4), 16) || 99;
  const b = parseInt(h.substring(4, 6), 16) || 235;
  return `rgba(${r}, ${g}, ${b}, ${alpha})`;
}

export default function CompareModal({ ids = [], jobId = null, onClose }) {
  const [loading, setLoading] = useState(false);
  const [candidates, setCandidates] = useState([]);
  const [jobSkills, setJobSkills] = useState([]);

  useEffect(() => {
    if (!jobId || !ids?.length) {
      setCandidates([]);
      return;
    }

    let isMounted = true;

    async function fetchComparisonData() {
      setLoading(true);
      try {
        const rawUserId = localStorage.getItem("user_id");
        const role = (localStorage.getItem("role") || "").toLowerCase().trim();
        const userId = Number(rawUserId);

        if (!rawUserId || isNaN(userId) || userId <= 0) {
          if (isMounted) setCandidates([]);
          return;
        }

        const res = await api.get(`/api/jobs/${jobId}/summary`, {
          params: { user_id: userId, role }
        });

        if (!isMounted) return;

        const allCandidates = res.data?.candidates || [];
        setJobSkills(res.data?.job_skills || []);
        const selected = allCandidates.filter((c) => ids.includes(c.candidate_id));
        setCandidates(selected);
      } catch (err) {
        console.error("Failed to load candidate comparison", err);
        if (isMounted) setCandidates([]);
      } finally {
        if (isMounted) setLoading(false);
      }
    }

    fetchComparisonData();

    return () => {
      isMounted = false;
    };
  }, [ids, jobId]);

  const barData = useMemo(() => ({
    labels: candidates.map((c) => c.candidate_name || `Applicant #${c.candidate_id}`),
    datasets: [
      {
        label: "Matched Skills",
        data: candidates.map((c) => (c.matched_skills || []).length),
        backgroundColor: "#10b981",
        stack: "stackGroup",
      },
      {
        label: "Skill Gaps",
        data: candidates.map((c) => (c.missing_skills || []).length),
        backgroundColor: "#ef4444",
        stack: "stackGroup",
      },
    ],
  }), [candidates]);

  const barOptions = useMemo(() => ({
    responsive: true,
    maintainAspectRatio: false,
    scales: {
      x: { stacked: true },
      y: { stacked: true, beginAtZero: true, ticks: { precision: 0 } },
    },
    plugins: {
      legend: {
        position: "top",
        labels: { boxWidth: 12, color: "#334155", font: { size: 12, weight: "600" } },
      },
    },
  }), []);

  if (!ids?.length) return null;

  return (
    <div className="cm-backdrop" onClick={onClose}>
      <div className="cm-modal" onClick={(e) => e.stopPropagation()}>
        <div className="cm-header">
          <div>
            <h3 style={{ margin: 0, fontSize: 18, color: "#0f172a" }}>Comparative Candidate Analysis</h3>
            <div style={{ fontSize: 12, color: "#64748b", marginTop: 2 }}>
              Evaluating {candidates.length} profiles against Requisition #{jobId}
            </div>
          </div>
          <button className="cm-close" onClick={onClose}>
            ✕ Close
          </button>
        </div>

        {loading ? (
          <div style={{ padding: 40, textAlign: "center", color: "#64748b" }}>
            Aggregating evaluation vectors...
          </div>
        ) : (
          <>
            <div className="cm-summary">
              {candidates.map((c) => (
                <div key={c.candidate_id} className="cm-card">
                  <div style={{ fontWeight: 700, color: "#0f172a" }}>
                    {c.candidate_name || `Applicant #${c.candidate_id}`}
                  </div>
                  <div style={{ marginTop: 6, fontSize: 13, color: "#475569" }}>
                    Fit Score: <strong style={{ color: "#2563eb" }}>{Math.round((c.score || 0) * 100)}%</strong> — Coverage {c.coverage_percent}%
                  </div>

                  <div style={{ marginTop: 8 }}>
                    <div style={{ fontSize: 11, fontWeight: 700, color: "#059669", textTransform: "uppercase" }}>
                      Matched Competencies ({c.matched_skills?.length || 0})
                    </div>
                    <div style={{ marginTop: 4, display: "flex", flexWrap: "wrap", gap: 4 }}>
                      {(c.matched_skills || []).length > 0 ? (
                        c.matched_skills.map((s) => (
                          <span key={s} className="chip chip-matched" style={{ fontSize: 11, padding: "2px 6px" }}>
                            {s}
                          </span>
                        ))
                      ) : (
                        <span style={{ color: "#94a3b8", fontSize: 12 }}>—</span>
                      )}
                    </div>
                  </div>

                  <div style={{ marginTop: 8 }}>
                    <div style={{ fontSize: 11, fontWeight: 700, color: "#be123c", textTransform: "uppercase" }}>
                      Skill Gaps ({c.missing_skills?.length || 0})
                    </div>
                    <div style={{ marginTop: 4, display: "flex", flexWrap: "wrap", gap: 4 }}>
                      {(c.missing_skills || []).length > 0 ? (
                        c.missing_skills.map((s) => (
                          <span key={s} className="chip chip-missing" style={{ fontSize: 11, padding: "2px 6px" }}>
                            {s}
                          </span>
                        ))
                      ) : (
                        <span style={{ color: "#059669", fontSize: 12 }}>All matched</span>
                      )}
                    </div>
                  </div>
                </div>
              ))}
            </div>

            <div className="cm-charts-row">
              <div className="cm-radar-grid">
                {candidates.map((c, idx) => {
                  const color = PALETTE[idx % PALETTE.length];
                  const radarData = {
                    labels: jobSkills,
                    datasets: [
                      {
                        label: c.candidate_name,
                        data: c.coverage_vector || jobSkills.map(() => 0),
                        backgroundColor: hexToRGBA(color, 0.2),
                        borderColor: hexToRGBA(color, 1),
                        borderWidth: 1.5,
                      },
                    ],
                  };

                  const radarOptions = {
                    maintainAspectRatio: false,
                    responsive: true,
                    plugins: { legend: { display: false } },
                    scales: {
                      r: {
                        ticks: { display: false, stepSize: 1, beginAtZero: true, max: 1 },
                        grid: { color: "rgba(0, 0, 0, 0.05)" },
                      },
                    },
                  };

                  return (
                    <div key={c.candidate_id} className="cm-radar-card">
                      <div style={{ fontWeight: 700, fontSize: 13, marginBottom: 6, color: "#0f172a" }}>
                        {c.candidate_name}
                      </div>
                      <div style={{ height: 180 }}>
                        <Radar data={radarData} options={radarOptions} />
                      </div>
                      <div style={{ marginTop: 8, fontSize: 12, color: "#64748b" }}>
                        Coverage: {c.coverage_percent}% • Matched: {(c.matched_skills || []).length} / {jobSkills.length}
                      </div>
                    </div>
                  );
                })}
              </div>

              <div className="cm-bar-box">
                <h4 style={{ margin: "0 0 10px 0", fontSize: 14, fontWeight: 700, color: "#0f172a" }}>
                  Skill Overlap vs. Gaps (Stacked)
                </h4>
                <div style={{ height: 320 }}>
                  <Bar data={barData} options={barOptions} />
                </div>
              </div>
            </div>
          </>
        )}
      </div>
    </div>
  );
}

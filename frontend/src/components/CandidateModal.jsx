import React from "react";
import { Radar } from "react-chartjs-2";
import {
  Chart as ChartJS,
  RadialLinearScale,
  PointElement,
  LineElement,
  Filler,
  Tooltip,
  Legend
} from "chart.js";
import { API_BASE_URL } from "../api";

ChartJS.register(
  RadialLinearScale,
  PointElement,
  LineElement,
  Filler,
  Tooltip,
  Legend
);

const COLORS = [
  "#2563eb", "#059669", "#db2777", "#d97706", "#8b5cf6",
  "#e11d48", "#0ea5a6", "#1f2937", "#065f46", "#BE185D"
];

function hexToRGBA(hex, alpha = 1) {
  const h = hex.replace("#", "");
  const r = parseInt(h.substring(0, 2), 16) || 37;
  const g = parseInt(h.substring(2, 4), 16) || 99;
  const b = parseInt(h.substring(4, 6), 16) || 235;
  return `rgba(${r}, ${g}, ${b}, ${alpha})`;
}

export default function CandidateModal({ candidate = null, jobSkills = [], onClose }) {
  if (!candidate) return null;

  const color = COLORS[(candidate.candidate_id || 0) % COLORS.length];

  const radarData = {
    labels: jobSkills.length > 0 ? jobSkills : ["General Profile"],
    datasets: [{
      label: candidate.candidate_name || "Candidate",
      data: candidate.coverage_vector?.length > 0 ? candidate.coverage_vector : [1],
      backgroundColor: hexToRGBA(color, 0.2),
      borderColor: hexToRGBA(color, 1),
      borderWidth: 2,
      pointBackgroundColor: hexToRGBA(color, 1)
    }]
  };

  return (
    <div
      style={{
        position: "fixed",
        inset: 0,
        background: "rgba(15, 23, 42, 0.65)",
        backdropFilter: "blur(4px)",
        display: "flex",
        justifyContent: "center",
        alignItems: "center",
        zIndex: 9999,
        padding: 16
      }}
      onClick={onClose}
    >
      <div
        style={{
          width: "100%",
          maxWidth: 840,
          background: "#fff",
          borderRadius: 16,
          padding: 24,
          boxShadow: "0 25px 60px rgba(0,0,0,0.25)",
          maxHeight: "90vh",
          overflowY: "auto"
        }}
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", borderBottom: "1px solid #e2e8f0", paddingBottom: 14 }}>
          <div>
            <h2 style={{ margin: 0, color: "#0f172a", fontSize: 20 }}>
              {candidate.candidate_name || `Candidate #${candidate.candidate_id}`}
            </h2>
            <div className="small" style={{ marginTop: 4 }}>
              Candidate ID: #{candidate.candidate_id} • Resume ID: #{candidate.resume_id}
            </div>
          </div>

          <div style={{ display: "flex", gap: 10, alignItems: "center" }}>
            <a
              href={`${API_BASE_URL}/api/resumes/${candidate.resume_id}/download`}
              target="_blank"
              rel="noreferrer"
              className="btn secondary"
              style={{ textDecoration: "none", padding: "8px 14px", fontSize: 13 }}
            >
              📄 Download Resume
            </a>
            <button
              onClick={onClose}
              style={{
                background: "#f1f5f9",
                border: "none",
                borderRadius: "8px",
                padding: "8px 12px",
                cursor: "pointer",
                fontWeight: 700,
                fontSize: 14
              }}
            >
              ✕
            </button>
          </div>
        </div>

        {/* Content Body */}
        <div style={{ display: "grid", gridTemplateColumns: "1fr 340px", gap: 20, marginTop: 20 }}>
          {/* Left Details Column */}
          <div>
            <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 10, marginBottom: 16 }}>
              <div style={{ background: "#f8fafc", padding: 12, borderRadius: 10, border: "1px solid #e2e8f0", textAlign: "center" }}>
                <div className="small">AI Match Score</div>
                <div style={{ fontSize: 22, fontWeight: 800, color: "#2563eb", marginTop: 4 }}>
                  {(candidate.score ?? 0).toFixed(3)}
                </div>
              </div>
              <div style={{ background: "#f8fafc", padding: 12, borderRadius: 10, border: "1px solid #e2e8f0", textAlign: "center" }}>
                <div className="small">Skill Overlap</div>
                <div style={{ fontSize: 22, fontWeight: 800, color: "#10b981", marginTop: 4 }}>
                  {Math.round((candidate.skill_score ?? 0) * 100)}%
                </div>
              </div>
              <div style={{ background: "#f8fafc", padding: 12, borderRadius: 10, border: "1px solid #e2e8f0", textAlign: "center" }}>
                <div className="small">Semantic Similarity</div>
                <div style={{ fontSize: 22, fontWeight: 800, color: "#8b5cf6", marginTop: 4 }}>
                  {Math.round((candidate.semantic ?? 0) * 100)}%
                </div>
              </div>
            </div>

            <div style={{ marginBottom: 14 }}>
              <div style={{ fontWeight: 700, fontSize: 14, color: "#166534", marginBottom: 6 }}>
                ✅ Matched Skills:
              </div>
              <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
                {(candidate.matched_skills || []).length > 0 ? (
                  candidate.matched_skills.map((s) => (
                    <span key={s} className="chip matched" style={{ margin: 0 }}>
                      {s}
                    </span>
                  ))
                ) : (
                  <span style={{ color: "#94a3b8", fontSize: 13 }}>No direct skill overlaps detected.</span>
                )}
              </div>
            </div>

            <div>
              <div style={{ fontWeight: 700, fontSize: 14, color: "#991b1b", marginBottom: 6 }}>
                ❌ Missing Skills:
              </div>
              <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
                {(candidate.missing_skills || []).length > 0 ? (
                  candidate.missing_skills.map((s) => (
                    <span key={s} className="chip missing" style={{ margin: 0 }}>
                      {s}
                    </span>
                  ))
                ) : (
                  <span style={{ color: "#166534", fontSize: 13 }}>All required job skills are covered!</span>
                )}
              </div>
            </div>
          </div>

          {/* Right Radar Visualization Column */}
          <div style={{ background: "#f8fafc", padding: 16, borderRadius: 12, border: "1px solid #e2e8f0" }}>
            <h4 style={{ margin: "0 0 10px 0", fontSize: 14, color: "#334155", textAlign: "center" }}>
              Skill Coverage Radar
            </h4>
            <div style={{ height: 240 }}>
              <Radar
                data={radarData}
                options={{
                  maintainAspectRatio: false,
                  responsive: true,
                  scales: {
                    r: {
                      ticks: { stepSize: 1, beginAtZero: true, max: 1, display: false },
                      suggestedMin: 0,
                      suggestedMax: 1
                    }
                  },
                  plugins: {
                    legend: { display: false }
                  }
                }}
              />
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

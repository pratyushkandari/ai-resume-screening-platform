import React from "react";
import { API_BASE_URL } from "../api";

export default function CandidateCard({
  candidate,
  isSelected = false,
  onViewRadar,
  onToggleCompare
}) {
  if (!candidate) return null;

  return (
    <div className="cand-card">
      <div className="cand-header">
        <div>
          <div className="cand-title">
            {candidate.candidate_name || `Candidate #${candidate.candidate_id}`}
          </div>
          <div className="cand-meta" style={{ marginTop: 4 }}>
            Score: <strong style={{ color: "#2563eb", fontSize: "15px" }}>{(candidate.score ?? 0).toFixed(3)}</strong>
            <span style={{ margin: "0 6px", color: "#cbd5e1" }}>|</span>
            Coverage: <strong>{candidate.coverage_percent}%</strong>
          </div>
        </div>

        <div style={{ display: "flex", flexDirection: "column", gap: 6, alignItems: "flex-end" }}>
          <div
            style={{
              padding: "4px 8px",
              borderRadius: 6,
              background: candidate.status === "accepted" ? "#dcfce7" : "#fee2e2",
              color: candidate.status === "accepted" ? "#166534" : "#991b1b",
              fontWeight: "700",
              fontSize: "11px",
              textTransform: "uppercase"
            }}
          >
            {candidate.status === "accepted" ? "✅ Shortlisted" : "❌ Rejected"}
          </div>
        </div>
      </div>

      <div style={{ marginTop: 10, fontSize: 13, display: "grid", gap: 4 }}>
        <div>
          <strong style={{ color: "#166534" }}>Matched:</strong>{" "}
          {(candidate.matched_skills || []).length > 0 ? (
            candidate.matched_skills.map((s) => (
              <span key={s} className="chip matched" style={{ fontSize: 11, padding: "2px 6px", margin: "2px" }}>
                {s}
              </span>
            ))
          ) : (
            <span style={{ color: "#94a3b8" }}>None</span>
          )}
        </div>
        <div>
          <strong style={{ color: "#991b1b" }}>Missing:</strong>{" "}
          {(candidate.missing_skills || []).length > 0 ? (
            candidate.missing_skills.map((s) => (
              <span key={s} className="chip missing" style={{ fontSize: 11, padding: "2px 6px", margin: "2px" }}>
                {s}
              </span>
            ))
          ) : (
            <span style={{ color: "#166534" }}>All matched</span>
          )}
        </div>
      </div>

      <div
        style={{
          marginTop: 12,
          paddingTop: 10,
          borderTop: "1px solid #f1f5f9",
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center"
        }}
      >
        <div style={{ display: "flex", gap: 8 }}>
          {onViewRadar && (
            <button
              onClick={() => onViewRadar(candidate)}
              className="btn secondary"
              style={{ padding: "5px 10px", fontSize: 12 }}
            >
              🔍 Radar View
            </button>
          )}
          {onToggleCompare && (
            <button
              onClick={() => onToggleCompare(candidate.candidate_id)}
              className="btn ghost"
              style={{
                padding: "5px 10px",
                fontSize: 12,
                background: isSelected ? "#e0f2fe" : "",
                borderColor: isSelected ? "#0284c7" : ""
              }}
            >
              {isSelected ? "✓ Selected" : "+ Compare"}
            </button>
          )}
        </div>

        <a
          href={`${API_BASE_URL}/api/resumes/${candidate.resume_id}/download`}
          target="_blank"
          rel="noopener noreferrer"
          className="link"
          style={{ fontSize: 12 }}
        >
          📄 Download
        </a>
      </div>
    </div>
  );
}

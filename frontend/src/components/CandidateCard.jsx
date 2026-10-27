import { toast } from "react-toastify";
import { downloadResume, getErrorMessage } from "../api";

/**
 * One applicant on the recruiter dashboard: score bar, Shortlisted / Under Review
 * badge, matched and missing skills, and actions (fit dialog, compare, download).
 *
 * @param {object} props
 * @param {object} props.candidate - One entry of `summary.candidates` from the API.
 * @param {boolean} [props.isSelected] - Whether it is selected for comparison.
 * @param {(candidate: object) => void} [props.onViewRadar] - Opens the fit dialog.
 * @param {(resumeId: number) => void} [props.onToggleCompare] - Adds/removes it from the comparison.
 */
export default function CandidateCard({
  candidate,
  isSelected = false,
  onViewRadar,
  onToggleCompare
}) {
  if (!candidate) return null;

  const matchPercent = Math.round((candidate.score ?? 0) * 100);
  const onDownload = () =>
    downloadResume(candidate.resume_id, candidate.filename || "resume").catch((err) =>
      toast.error(getErrorMessage(err, "Could not download the resume."))
    );
  const isShortlisted = candidate.status === "accepted";

  return (
    <div
      className="candidate-item-card"
      style={{
        border: isSelected ? "1.5px solid #3b82f6" : "1px solid #e2e8f0",
        backgroundColor: isSelected ? "#f8faff" : "#ffffff"
      }}
    >
      <div>
        {/* Header: Candidate Name & Status Pill */}
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", gap: 8 }}>
          <div>
            <div style={{ fontWeight: 700, fontSize: "15px", color: "#0f172a" }}>
              {candidate.candidate_name || `Applicant #${candidate.candidate_id}`}
            </div>
            <div style={{ fontSize: "12px", color: "#64748b", marginTop: 2 }}>
              Coverage: <strong style={{ color: "#334155" }}>{candidate.coverage_percent}%</strong>
            </div>
          </div>

          <div
            style={{
              display: "inline-flex",
              alignItems: "center",
              gap: 5,
              padding: "3px 8px",
              borderRadius: 6,
              fontSize: "11px",
              fontWeight: 700,
              backgroundColor: isShortlisted ? "#ecfdf5" : "#f1f5f9",
              color: isShortlisted ? "#047857" : "#475569",
              border: `1px solid ${isShortlisted ? "#a7f3d0" : "#e2e8f0"}`
            }}
          >
            <span
              style={{
                width: 6,
                height: 6,
                borderRadius: "50%",
                backgroundColor: isShortlisted ? "#10b981" : "#94a3b8"
              }}
            />
            {isShortlisted ? "Shortlisted" : "Under Review"}
          </div>
        </div>

        {/* Score Progress Bar */}
        <div style={{ marginTop: 12, marginBottom: 14 }}>
          <div style={{ display: "flex", justifyContent: "space-between", fontSize: "12px", marginBottom: 4 }}>
            <span style={{ color: "#64748b", fontWeight: 500 }}>Match Score</span>
            {/* Green follows the API's Shortlisted decision, like the badge above. */}
            <span style={{ fontWeight: 700, color: isShortlisted ? "#047857" : "#2563eb" }}>
              {matchPercent}%
            </span>
          </div>
          <div style={{ height: 6, width: "100%", backgroundColor: "#f1f5f9", borderRadius: 3, overflow: "hidden" }}>
            <div
              style={{
                height: "100%",
                width: `${matchPercent}%`,
                backgroundColor: isShortlisted ? "#10b981" : "#3b82f6",
                borderRadius: 3
              }}
            />
          </div>
        </div>

        {/* Matched & Missing Skills */}
        <div style={{ fontSize: 12, display: "grid", gap: 8 }}>
          <div>
            <div style={{ fontWeight: 600, color: "#334155", marginBottom: 3 }}>Matched Skills:</div>
            <div style={{ display: "flex", flexWrap: "wrap", gap: 4 }}>
              {(candidate.matched_skills || []).length > 0 ? (
                candidate.matched_skills.map((s) => (
                  <span key={s} className="chip chip-matched" style={{ fontSize: 11, padding: "2px 7px" }}>
                    {s}
                  </span>
                ))
              ) : (
                <span style={{ color: "#64748b", fontStyle: "italic" }}>None detected</span>
              )}
            </div>
          </div>

          <div>
            <div style={{ fontWeight: 600, color: "#64748b", marginBottom: 3 }}>Skill Gaps:</div>
            <div style={{ display: "flex", flexWrap: "wrap", gap: 4 }}>
              {(candidate.missing_skills || []).length > 0 ? (
                candidate.missing_skills.map((s) => (
                  <span key={s} className="chip chip-missing" style={{ fontSize: 11, padding: "2px 7px" }}>
                    {s}
                  </span>
                ))
              ) : (
                <span style={{ color: "#047857", fontWeight: 500 }}>All requirements satisfied</span>
              )}
            </div>
          </div>
        </div>
      </div>

      {/* Footer Actions */}
      <div
        style={{
          marginTop: 16,
          paddingTop: 12,
          borderTop: "1px solid #f1f5f9",
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center"
        }}
      >
        <div style={{ display: "flex", gap: 6 }}>
          {onViewRadar && (
            <button
              type="button"
              onClick={() => onViewRadar(candidate)}
              className="btn btn-secondary"
              style={{ padding: "5px 9px", fontSize: 11, borderRadius: 5 }}
            >
              <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <circle cx="12" cy="12" r="10"/>
                <path d="M12 2a14.5 14.5 0 0 0 0 20 14.5 14.5 0 0 0 0-20"/>
                <path d="M2 12h20"/>
              </svg>
              View Fit
            </button>
          )}

          {onToggleCompare && (
            <button
              type="button"
              aria-pressed={isSelected}
              onClick={() => onToggleCompare(candidate.resume_id)}
              className="btn"
              style={{
                padding: "5px 9px",
                fontSize: 11,
                borderRadius: 5,
                backgroundColor: isSelected ? "#dbeafe" : "#f8fafc",
                color: isSelected ? "#1e40af" : "#475569",
                border: isSelected ? "1px solid #bfdbfe" : "1px solid #cbd5e1"
              }}
            >
              {isSelected ? "Selected" : "+ Compare"}
            </button>
          )}
        </div>

        <button
          type="button"
          onClick={onDownload}
          aria-label={`Download resume of ${candidate.candidate_name || "candidate"}`}
          style={{
            background: "transparent",
            border: "none",
            cursor: "pointer",
            padding: 0,
            display: "inline-flex",
            alignItems: "center",
            gap: 4,
            fontSize: 12,
            fontWeight: 600,
            color: "#2563eb",
            textDecoration: "none"
          }}
        >
          <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>
            <polyline points="7 10 12 15 17 10"/>
            <line x1="12" x2="12" y1="15" y2="3"/>
          </svg>
          Resume
        </button>
      </div>
    </div>
  );
}

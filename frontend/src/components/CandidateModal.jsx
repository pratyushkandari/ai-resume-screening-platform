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
import { toast } from "react-toastify";
import { downloadResume, getErrorMessage } from "../api";
import { colorAt, hexToRGBA } from "../theme";
import Modal from "./Modal";

ChartJS.register(
  RadialLinearScale,
  PointElement,
  LineElement,
  Filler,
  Tooltip,
  Legend
);

/**
 * "View Fit" dialog for one applicant: overall, skill and semantic scores, matched
 * and missing skills, a radar chart of required-skill coverage and a download button.
 *
 * @param {object} props
 * @param {object|null} props.candidate - Entry from `summary.candidates`; nothing renders when null.
 * @param {string[]} props.jobSkills - Required skills, in the same order as `coverage_vector`.
 * @param {() => void} props.onClose - Called on Escape, backdrop click or the close button.
 */
export default function CandidateModal({ candidate = null, jobSkills = [], onClose }) {
  if (!candidate) return null;

  const color = colorAt(candidate.candidate_id || 0);
  const title = candidate.candidate_name || `Candidate #${candidate.candidate_id}`;

  const onDownload = () =>
    downloadResume(candidate.resume_id, candidate.filename || "resume").catch((err) =>
      toast.error(getErrorMessage(err, "Could not download the resume."))
    );

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
    <Modal title={`Candidate fit: ${title}`} onClose={onClose} width={840}>
        {/* Header */}
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", borderBottom: "1px solid #e2e8f0", paddingBottom: 14 }}>
          <div>
            <h2 style={{ margin: 0, color: "#0f172a", fontSize: 20 }}>
              {title}
            </h2>
            <div className="small" style={{ marginTop: 4 }}>
              Candidate ID: #{candidate.candidate_id} • Resume ID: #{candidate.resume_id}
            </div>
          </div>

          <div style={{ display: "flex", gap: 10, alignItems: "center" }}>
            <button
              type="button"
              onClick={onDownload}
              className="btn btn-secondary"
              style={{ padding: "8px 14px", fontSize: 13 }}
            >
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>
                <polyline points="7 10 12 15 17 10"/>
                <line x1="12" x2="12" y1="15" y2="3"/>
              </svg>
              Download Resume
            </button>
            <button
              type="button"
              aria-label="Close"
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
        <div className="modal-body-grid">
          {/* Left Details Column */}
          <div>
            <div style={{ display: "grid", gridTemplateColumns: "repeat(3, minmax(0, 1fr))", gap: 10, marginBottom: 16 }}>
              <div style={{ background: "#f8fafc", padding: 12, borderRadius: 10, border: "1px solid #e2e8f0", textAlign: "center" }}>
                <div className="small">Overall Match Score</div>
                <div style={{ fontSize: 22, fontWeight: 800, color: "#2563eb", marginTop: 4 }}>
                  {Math.round((candidate.score ?? 0) * 100)}%
                </div>
              </div>
              <div style={{ background: "#f8fafc", padding: 12, borderRadius: 10, border: "1px solid #e2e8f0", textAlign: "center" }}>
                <div className="small">Skill Fit</div>
                <div style={{ fontSize: 22, fontWeight: 800, color: "#059669", marginTop: 4 }}>
                  {Math.round((candidate.skill_score ?? 0) * 100)}%
                </div>
              </div>
              <div style={{ background: "#f8fafc", padding: 12, borderRadius: 10, border: "1px solid #e2e8f0", textAlign: "center" }}>
                <div className="small">Semantic Fit</div>
                <div style={{ fontSize: 22, fontWeight: 800, color: "#8b5cf6", marginTop: 4 }}>
                  {Math.round((candidate.semantic ?? 0) * 100)}%
                </div>
              </div>
            </div>

            <div style={{ marginBottom: 14 }}>
              <div style={{ fontWeight: 600, fontSize: 13, color: "#047857", marginBottom: 6 }}>
                Matched Skills:
              </div>
              <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
                {(candidate.matched_skills || []).length > 0 ? (
                  candidate.matched_skills.map((s) => (
                    <span key={s} className="chip chip-matched">
                      {s}
                    </span>
                  ))
                ) : (
                  <span style={{ color: "#64748b", fontSize: 13 }}>No direct skill overlaps detected.</span>
                )}
              </div>
            </div>

            <div>
              <div style={{ fontWeight: 600, fontSize: 13, color: "#be123c", marginBottom: 6 }}>
                Identified Skill Gaps:
              </div>
              <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
                {(candidate.missing_skills || []).length > 0 ? (
                  candidate.missing_skills.map((s) => (
                    <span key={s} className="chip chip-missing">
                      {s}
                    </span>
                  ))
                ) : (
                  <span style={{ color: "#047857", fontSize: 13 }}>All required competencies are satisfied</span>
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
                role="img"
                aria-label={`Radar chart of required skill coverage for ${title}`}
                data={radarData}
                options={{
                  maintainAspectRatio: false,
                  responsive: true,
                  scales: {
                    r: { min: 0, max: 1, ticks: { stepSize: 1, display: false } }
                  },
                  plugins: {
                    legend: { display: false }
                  }
                }}
              />
            </div>
          </div>
        </div>
    </Modal>
  );
}

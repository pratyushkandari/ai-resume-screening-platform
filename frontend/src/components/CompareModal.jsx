import { useMemo } from "react";
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
import { colorAt, hexToRGBA } from "../theme";
import Modal from "./Modal";
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

/**
 * Side-by-side comparison of two or more applicants already loaded by the
 * dashboard (no extra API call): summary cards, one radar per applicant and a
 * stacked bar of matched skills vs. gaps.
 *
 * @param {object} props
 * @param {object[]} props.candidates - Selected entries of `summary.candidates`.
 * @param {string[]} props.jobSkills - Required skills (radar axes).
 * @param {number|null} props.jobId - Shown in the header.
 * @param {() => void} props.onClose - Closes the dialog.
 */
export default function CompareModal({ candidates = [], jobSkills = [], jobId = null, onClose }) {
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

  if (!candidates.length) return null;

  return (
    <Modal title="Compare candidates" onClose={onClose} className="cm-modal" backdropClassName="cm-backdrop">
        <div className="cm-header">
          <div>
            <h3 style={{ margin: 0, fontSize: 18, color: "#0f172a" }}>Comparative Candidate Analysis</h3>
            <div style={{ fontSize: 12, color: "#64748b", marginTop: 2 }}>
              Evaluating {candidates.length} profiles against Requisition #{jobId}
            </div>
          </div>
          <button type="button" className="cm-close" onClick={onClose}>
            ✕ Close
          </button>
        </div>

            <div className="cm-summary">
              {candidates.map((c) => (
                <div key={c.resume_id} className="cm-card">
                  <div style={{ fontWeight: 700, color: "#0f172a" }}>
                    {c.candidate_name || `Applicant #${c.candidate_id}`}
                  </div>
                  <div style={{ marginTop: 6, fontSize: 13, color: "#475569" }}>
                    Fit Score: <strong style={{ color: "#2563eb" }}>{Math.round((c.score || 0) * 100)}%</strong> — Coverage {c.coverage_percent}%
                  </div>

                  <div style={{ marginTop: 8 }}>
                    <div style={{ fontSize: 11, fontWeight: 700, color: "#047857", textTransform: "uppercase" }}>
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
                        <span style={{ color: "#64748b", fontSize: 12 }}>—</span>
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
                        <span style={{ color: "#047857", fontSize: 12 }}>All matched</span>
                      )}
                    </div>
                  </div>
                </div>
              ))}
            </div>

            <div className="cm-charts-row">
              <div className="cm-radar-grid">
                {candidates.map((c, idx) => {
                  const color = colorAt(idx);
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
                        min: 0,
                        max: 1,
                        ticks: { display: false, stepSize: 1 },
                        grid: { color: "rgba(0, 0, 0, 0.05)" },
                      },
                    },
                  };

                  return (
                    <div key={c.resume_id} className="cm-radar-card">
                      <div style={{ fontWeight: 700, fontSize: 13, marginBottom: 6, color: "#0f172a" }}>
                        {c.candidate_name}
                      </div>
                      <div style={{ height: 180 }}>
                        <Radar role="img" data={radarData} options={radarOptions} aria-label={`Skill coverage radar for ${c.candidate_name}`} />
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
                  <Bar role="img" data={barData} options={barOptions} aria-label="Stacked bar chart of matched skills and skill gaps per candidate" />
                </div>
              </div>
            </div>
    </Modal>
  );
}

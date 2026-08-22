

// ---------------------------------------------------------------------------------------------
//  STEP 1️: IMPORT ALL REQUIRED LIBRARIES
// ---------------------------------------------------------------------------------------------
import React, { useEffect, useState } from "react";  // React + Hooks for state & lifecycle mgmt
import api from "../api";                           // Pre-configured Axios instance for backend
import { Radar, Bar } from "react-chartjs-2";       // Chart components to render data visualizations

// Import core building blocks of Chart.js used to draw radar & bar charts
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

//  Import CSS file to apply layout, colors, modal styles defined separately
import "./CompareModal.css";



ChartJS.register(
  RadialLinearScale, // circular coordinate grid for radar
  PointElement,      // dots in charts
  LineElement,       // lines connecting points in radar
  Filler,            // color filling under radar area
  Tooltip,           // tooltips on hover
  Legend,            // chart legend display
  CategoryScale,     // x-axis labels for bar chart
  LinearScale,       // y-axis numerical values
  BarElement         // bars for bar chart
);



const COLORS = [
  "#2563eb", "#059669", "#db2777", "#d97706",
  "#8b5cf6", "#e11d48", "#0ea5a6", "#1f2937",
  "#065f46", "#BE185D"
];



function hexToRGBA(hex, alpha = 1) {
  const h = hex.replace("#", "");
  const r = parseInt(h.substring(0, 2), 16);
  const g = parseInt(h.substring(2, 4), 16);
  const b = parseInt(h.substring(4, 6), 16);
  return `rgba(${r}, ${g}, ${b}, ${alpha})`;
}



export default function CompareModal({ ids = [], jobId = null, onClose }) {

  // -------------------------------------------------------------------------------------------
  //  STATE VARIABLES (React’s useState)
  // -------------------------------------------------------------------------------------------
  const [loading, setLoading] = useState(false);    // “true” while data is loading
  const [candidates, setCandidates] = useState([]); // stores selected candidates’ info
  const [jobSkills, setJobSkills] = useState([]);   // stores list of job-required skills



  useEffect(() => {
    if (!jobId || !ids?.length) {
      setCandidates([]); // reset if no selection
      return;
    }

    // Immediately invoked async function
    (async () => {
      setLoading(true); // start loader
      try {
// ✅ GET SESSION DATA
const raw_user_id = localStorage.getItem("user_id");
const role = (localStorage.getItem("role") || "").toLowerCase().trim();
const user_id = Number(raw_user_id);

// ✅ VALIDATION
if (!raw_user_id || isNaN(user_id) || user_id <= 0) {
  console.error("Invalid session");
  setCandidates([]);
  return;
}

// ✅ FIXED API CALL (THIS WAS CAUSING 422)
const res = await api.get(`/api/jobs/${jobId}/summary`, {
  params: {
    user_id: user_id,
    role: role
  }
});

// ✅ EXTRACT DATA
const allCandidates = res.data?.candidates || [];
setJobSkills(res.data?.job_skills || []);

// ✅ FILTER ONLY SELECTED IDS (IMPORTANT)
const selectedCandidates = allCandidates.filter(c =>
  ids.includes(c.candidate_id)
);

setCandidates(selectedCandidates);

      }
       catch (e) {
        console.error("Compare fetch error", e);
        setCandidates([]); // fallback to empty
      } finally {
        setLoading(false); // stop loader
      }
    })();
  }, [ids, jobId]);


  if (!ids?.length) return null;



  const barData = {
    labels: candidates.map(c => c.candidate_name),
    datasets: [
      {
        label: "Matched",
        data: candidates.map(c => (c.matched_skills || []).length),
        backgroundColor: "#4caf50",
        stack: "a"
      },
      {
        label: "Missing",
        data: candidates.map(c => (c.missing_skills || []).length),
        backgroundColor: "#f44336",
        stack: "a"
      }
    ]
  };

  const barOptions = {
    responsive: true,
    maintainAspectRatio: false,
    scales: {
      x: { stacked: true },
      y: { stacked: true, beginAtZero: true, ticks: { precision: 0 } }
    },
    plugins: { legend: { position: "top" } }
  };



  return (
    <div className="cm-backdrop">
      <div className="cm-modal">
        {/* ---------------- HEADER ---------------- */}
        <div className="cm-header">
          <h3>Compare Candidates</h3>
          <button className="cm-close" onClick={onClose}>Close</button>
        </div>

        {/* ---------------- MAIN CONTENT ---------------- */}
        {loading ? (
          <div style={{ padding: 12 }}>Loading...</div>
        ) : (
          <>
            {/* -----------------------------------------------------------
                🧾 CANDIDATE SUMMARY CARDS
               ----------------------------------------------------------- */}
            <div className="cm-summary">
              {candidates.map((c) => (
                <div key={c.candidate_id} className="cm-card">
                  <div style={{ fontWeight: 700 }}>{c.candidate_name}</div>
                  <div style={{ marginTop: 6, fontSize: 13 }}>
                    Score: {c.score} — Coverage {c.coverage_percent}%
                  </div>

                  {/* Matched Skills Section */}
                  <div style={{ marginTop: 8 }}>
                    <div style={{ fontSize: 12, fontWeight: 600 }}>Matched:</div>
                    <div style={{ marginTop: 6 }}>
                      {(c.matched_skills || []).length
                        ? c.matched_skills.map(s => (
                            <span key={s} className="chip matched">{s}</span>
                          ))
                        : <span style={{ color: "#777" }}>—</span>}
                    </div>
                  </div>

                  {/* Missing Skills Section */}
                  <div style={{ marginTop: 8 }}>
                    <div style={{ fontSize: 12, fontWeight: 600 }}>Missing:</div>
                    <div style={{ marginTop: 6 }}>
                      {(c.missing_skills || []).length
                        ? c.missing_skills.map(s => (
                            <span key={s} className="chip missing">{s}</span>
                          ))
                        : <span style={{ color: "#777" }}>—</span>}
                    </div>
                  </div>
                </div>
              ))}
            </div>

            {/* -----------------------------------------------------------
                📊 CHARTS SECTION
               ----------------------------------------------------------- */}
            <div className="cm-charts-row">

              {/* LEFT: RADAR CHARTS FOR EACH CANDIDATE */}
              <div className="cm-radar-grid">
                {candidates.map((c, idx) => {
                  const color = COLORS[idx % COLORS.length];

                  const radarData = {
                    labels: jobSkills,
                    datasets: [
                      {
                        label: c.candidate_name,
                        data: c.coverage_vector || jobSkills.map(() => 0),
                        backgroundColor: hexToRGBA(color, 0.18),
                        borderColor: hexToRGBA(color, 0.9),
                        borderWidth: 1
                      }
                    ]
                  };

                  const radarOptions = {
                    maintainAspectRatio: false,
                    responsive: true,
                    plugins: { legend: { display: false } },
                    scales: {
                      r: {
                        ticks: {
                          display: false,
                          stepSize: 1,
                          beginAtZero: true,
                          max: 1
                        },
                        grid: { color: "rgba(0,0,0,0.04)" }
                      }
                    }
                  };

                  return (
                    <div key={c.candidate_id} className="cm-radar-card">
                      <div style={{ fontWeight: 700, marginBottom: 6 }}>
                        {c.candidate_name}
                      </div>
                      <div style={{ height: 180 }}>
                        <Radar data={radarData} options={radarOptions} />
                      </div>
                      <div style={{ marginTop: 8, fontSize: 12, color: "#444" }}>
                        Matched: {(c.matched_skills || []).length} •
                        Missing: {(c.missing_skills || []).length}
                      </div>
                    </div>
                  );
                })}
              </div>

              {/* RIGHT: STACKED BAR CHART (Matched vs Missing) */}
              <div className="cm-bar-box">
                <h4 style={{ marginTop: 0 }}>Matched vs Missing (stacked)</h4>
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



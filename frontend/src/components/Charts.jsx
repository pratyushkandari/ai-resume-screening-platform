import { useMemo } from "react";
import { Bar, Doughnut, Scatter, Line } from "react-chartjs-2";
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  BarElement,
  ArcElement,
  PointElement,
  LineElement,
  Tooltip,
  Legend,
  Title,
} from "chart.js";
import { colorAt } from "../theme";

ChartJS.register(
  CategoryScale,
  LinearScale,
  BarElement,
  ArcElement,
  PointElement,
  LineElement,
  Tooltip,
  Legend,
  Title
);

/** Draw a ✓ or ✕ on a small white circle; used as point markers in the coverage chart. */
function renderMarkerCanvas(symbol, fillStyle) {
  const canvas = document.createElement("canvas");
  canvas.width = 28;
  canvas.height = 28;
  const ctx = canvas.getContext("2d");
  if (!ctx) return new Image();

  ctx.clearRect(0, 0, canvas.width, canvas.height);
  ctx.beginPath();
  ctx.arc(14, 14, 12, 0, Math.PI * 2);
  ctx.fillStyle = "rgba(255, 255, 255, 0.94)";
  ctx.fill();

  ctx.font = "600 15px -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif";
  ctx.textAlign = "center";
  ctx.textBaseline = "middle";
  ctx.fillStyle = fillStyle;
  ctx.fillText(symbol, 14, 14);

  const img = new Image();
  img.src = canvas.toDataURL();
  return img;
}

/**
 * Dashboard analytics for one job, computed only from the summary API response:
 * - bar: how many applicants have each required skill;
 * - doughnut: strong fits (≥75%), other shortlisted, under review;
 * - scatter: semantic fit vs. skill fit per applicant;
 * - line: which required skills each applicant covers (✓ / ✕).
 *
 * @param {object} props
 * @param {{skill_name: string, matches: number}[]} props.jobSkillCounts - `summary.job_skill_counts`.
 * @param {object[]} props.candidates - `summary.candidates`.
 */
export default function Charts({ jobSkillCounts = [], candidates = [] }) {
  const skillLabels = useMemo(
    () => jobSkillCounts.map((s) => s.skill_name || s.skill || "—"),
    [jobSkillCounts]
  );

  const [tickMarker, crossMarker] = useMemo(
    () => [
      renderMarkerCanvas("✓", "#10b981"),
      renderMarkerCanvas("✕", "#ef4444"),
    ],
    []
  );

  const barData = useMemo(() => ({
    labels: skillLabels,
    datasets: [
      {
        label: "Candidates with skill",
        data: jobSkillCounts.map((s) => s.matches || 0),
        backgroundColor: "rgba(37, 99, 235, 0.8)",
        borderRadius: 4,
      },
    ],
  }), [skillLabels, jobSkillCounts]);

  const barOptions = useMemo(() => ({
    maintainAspectRatio: false,
    responsive: true,
    plugins: { legend: { display: false } },
    scales: {
      y: { beginAtZero: true, ticks: { precision: 0 } },
    },
    layout: { padding: { top: 8, bottom: 8 } },
  }), []);

  // Tiers follow the API's own decision (status "accepted" = Shortlisted), so the
  // chart can never disagree with the "Shortlisted" / "Under Review" badges.
  const qualityBuckets = useMemo(() => {
    const buckets = { high: 0, medium: 0, low: 0 };
    (candidates || []).forEach((c) => {
      if (c.status !== "accepted") buckets.low++;
      else if ((c.score || 0) >= 0.75) buckets.high++;
      else buckets.medium++;
    });
    return buckets;
  }, [candidates]);

  const donutData = useMemo(() => ({
    labels: ["Strong fit (≥75%)", "Shortlisted", "Under review"],
    datasets: [
      {
        data: [qualityBuckets.high, qualityBuckets.medium, qualityBuckets.low],
        backgroundColor: ["#10b981", "#f59e0b", "#ef4444"],
        borderWidth: 0,
      },
    ],
  }), [qualityBuckets]);

  const donutOptions = useMemo(() => ({
    maintainAspectRatio: false,
    responsive: true,
    cutout: "68%",
    plugins: {
      legend: {
        position: "top",
        labels: { boxWidth: 12, color: "#334155", font: { size: 12, weight: "600" } },
      },
      tooltip: {
        callbacks: {
          label: (ctx) => {
            const val = ctx.raw || 0;
            const total = ctx.dataset.data.reduce((a, b) => a + b, 0) || 1;
            const pct = Math.round((val / total) * 100);
            return `${ctx.label}: ${val} (${pct}%)`;
          },
        },
      },
    },
  }), []);

  const scatterData = useMemo(() => {
    const datasets = (candidates || []).map((c, idx) => {
      const color = colorAt(idx);
      const semanticPct = Math.round((c.semantic || 0) * 100);
      const skillPct = Math.round((c.skill_score || 0) * 100);
      const size = Math.max(6, Math.min(12, 6 + Math.round((c.score || 0) * 6)));
      return {
        label: c.candidate_name || `Applicant #${c.candidate_id}`,
        data: [{ x: semanticPct, y: skillPct }],
        backgroundColor: color,
        pointRadius: size,
        pointHoverRadius: size + 3,
      };
    });
    return { datasets };
  }, [candidates]);

  const scatterOptions = useMemo(() => ({
    maintainAspectRatio: false,
    responsive: true,
    scales: {
      x: { title: { display: true, text: "Semantic Fit (%)" }, min: 0, max: 100 },
      y: { title: { display: true, text: "Lexical Skill Fit (%)" }, min: 0, max: 100 },
    },
    plugins: {
      legend: { display: false },
    },
  }), []);

  const lineData = useMemo(() => {
    const datasets = (candidates || []).map((cand, idx) => {
      const color = colorAt(idx);
      const data = (cand.coverage_vector || []).map((v) => (v ? 1 : 0));
      return {
        label: cand.candidate_name || `Applicant #${cand.candidate_id}`,
        data,
        borderColor: color,
        borderWidth: 2,
        tension: 0, // straight segments: curves would overshoot above ✓ / below ✕
        showLine: true,
        fill: false,
        pointStyle: (ctx) => (ctx.raw === 1 ? tickMarker : crossMarker),
        pointRadius: 9,
        pointHoverRadius: 11,
      };
    });
    return { labels: skillLabels, datasets };
  }, [candidates, skillLabels, tickMarker, crossMarker]);

  const lineOptions = useMemo(() => ({
    responsive: true,
    maintainAspectRatio: false,
    plugins: { legend: { position: "top" } },
    scales: {
      x: { ticks: { autoSkip: false } },
      y: {
        min: -0.2,
        max: 1.2,
        ticks: {
          stepSize: 1,
          callback: (v) => (v === 1 ? "✓" : v === 0 ? "✕" : ""),
        },
      },
    },
  }), []);

  return (
    <div className="charts-root">
      <div className="charts-top">
        <div className="card" style={{ padding: 18, height: 340 }}>
          <h4 style={{ margin: "0 0 12px 0", fontSize: 15, fontWeight: 700, color: "#0f172a" }}>
            Requisition Skill Coverage Distribution
          </h4>
          <div style={{ height: 260 }}>
            {skillLabels.length ? (
              <Bar data={barData} options={barOptions} aria-label="Bar chart: number of candidates having each required skill" />
            ) : (
              <div style={{ color: "#64748b", padding: 40, textAlign: "center" }}>No skill constraints defined.</div>
            )}
          </div>
        </div>

        <div style={{ display: "grid", gridTemplateRows: "210px 250px", gridTemplateColumns: "minmax(0, 1fr)", gap: 14 }}>
          <div className="card" style={{ padding: 16 }}>
            <h4 style={{ margin: "0 0 8px 0", fontSize: 14, fontWeight: 700, color: "#0f172a" }}>
              Applicant Quality Breakdown
            </h4>
            <div style={{ width: "100%", height: 145 }}>
              <Doughnut data={donutData} options={donutOptions} aria-label={`Doughnut chart: ${qualityBuckets.high} strong fits (75% or more), ${qualityBuckets.medium} other shortlisted, ${qualityBuckets.low} under review`} />
            </div>
          </div>

          <div className="card" style={{ padding: 16 }}>
            <h4 style={{ margin: "0 0 8px 0", fontSize: 14, fontWeight: 700, color: "#0f172a" }}>
              Semantic vs. Lexical Match Matrix
            </h4>
            <div style={{ height: 185 }}>
              <Scatter data={scatterData} options={scatterOptions} aria-label="Scatter chart of semantic fit versus skill fit for each candidate" />
            </div>
          </div>
        </div>
      </div>

      <div className="card" style={{ padding: 18 }}>
        <h4 style={{ margin: "0 0 4px 0", fontSize: 15, fontWeight: 700, color: "#0f172a" }}>
          Candidate Coverage Vector Analysis
        </h4>
        <div style={{ color: "#64748b", marginBottom: 12, fontSize: 13 }}>
          Multi-dimensional skill matrix verification. Hover coordinates to inspect matched and gap indicators.
        </div>

        {skillLabels.length && candidates.length ? (
          <div style={{ height: 300 }}>
            <Line data={lineData} options={lineOptions} aria-label="Chart of which required skills each candidate covers" />
          </div>
        ) : (
          <div style={{ color: "#64748b", padding: 30, textAlign: "center" }}>
            No vector evaluation data available.
          </div>
        )}
      </div>
    </div>
  );
}

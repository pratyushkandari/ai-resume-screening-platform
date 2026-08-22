
import React, { useMemo } from "react";  // React core library + useMemo optimization hook
import { Bar, Doughnut, Scatter, Line } from "react-chartjs-2";  // 4 chart components from react-chartjs-2 wrapper

// Import base Chart.js modules (each chart type depends on several parts of Chart.js)
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


ChartJS.register(
  CategoryScale,   // x-axis (categorical)
  LinearScale,     // y-axis (numeric)
  BarElement,      // bars for bar chart
  ArcElement,      // arcs for donut chart
  PointElement,    // points for scatter and line charts
  LineElement,     // lines for line chart
  Tooltip,         // tooltip on hover
  Legend,          // chart legends
  Title            // chart titles
);



const COLORS = [
  "#2563eb", "#059669", "#db2777", "#d97706", "#8b5cf6",
  "#e11d48", "#0ea5a6", "#1f2937", "#065f46", "#BE185D"
];



function createMarkerImage(char, color) {
  // Create a small HTML <canvas> to draw on
  const c = document.createElement("canvas");
  c.width = 28; // width in pixels
  c.height = 28;

  // Get drawing context
  const ctx = c.getContext("2d");
  ctx.clearRect(0, 0, c.width, c.height); // clear any old drawing

  // Draw circular background (white with transparency)
  ctx.beginPath();
  ctx.arc(c.width / 2, c.height / 2, 12, 0, Math.PI * 2);
  ctx.fillStyle = "rgba(255,255,255,0.92)";
  ctx.fill();

  // Draw the ✓ or ✕ character in the center
  ctx.font = "16px sans-serif";
  ctx.textAlign = "center";
  ctx.textBaseline = "middle";
  ctx.fillStyle = color;
  ctx.fillText(char, c.width / 2, c.height / 2);

  // Convert the drawing to an image
  const img = new Image();
  img.src = c.toDataURL();
  return img;
}



export default function Charts({ jobSkillCounts = [], candidates = [] }) {


  const skillLabels = jobSkillCounts.map(
    (s) => s.skill_name || s.skill || "—"
  );


  const [tickImg, crossImg] = useMemo(
    () => [
      createMarkerImage("✓", "#10B981"), // green tick
      createMarkerImage("✕", "#EF4444"), // red cross
    ],
    []
  );


  const barData = {
    labels: skillLabels,
    datasets: [
      {
        label: "Candidates covering skill",
        data: jobSkillCounts.map((s) => s.matches || 0),
        backgroundColor: "rgba(54,162,235,0.78)", // blue bars
      },
    ],
  };

  // Chart options — control look & behavior
  const barOptions = {
    maintainAspectRatio: false,
    responsive: true,
    plugins: { legend: { display: false } },
    scales: {
      y: { beginAtZero: true, ticks: { precision: 0 } },
    },
    layout: { padding: { top: 8, bottom: 8 } },
  };


  const qualityBuckets = useMemo(() => {
    const buckets = { high: 0, medium: 0, low: 0 };
    (candidates || []).forEach((c) => {
      const pct = (c.score || 0) * 100;
      if (pct >= 75) buckets.high++;
      else if (pct >= 50) buckets.medium++;
      else buckets.low++;
    });
    return buckets;
  }, [candidates]);

  // Donut data + configuration
  const donutData = {
    labels: ["High (≥75%)", "Medium (50–74%)", "Low (<50%)"],
    datasets: [
      {
        data: [qualityBuckets.high, qualityBuckets.medium, qualityBuckets.low],
        backgroundColor: ["#10B981", "#F59E0B", "#EF4444"], // green, yellow, red
        borderWidth: 0,
      },
    ],
  };

  const donutOptions = {
    maintainAspectRatio: false,
    responsive: true,
    cutout: "65%", // makes it a donut (inner hole)
    plugins: {
      legend: {
        position: "top",
        labels: { boxWidth: 14, color: "#111", font: { size: 12, weight: "500" } },
      },
      tooltip: {
        callbacks: {
          label: function (ctx) {
            const val = ctx.raw || 0;
            const total = ctx.dataset.data.reduce((a, b) => a + b, 0) || 1;
            const pct = Math.round((val / total) * 100);
            return `${ctx.label}: ${val} (${pct}%)`;
          },
        },
      },
    },
    layout: { padding: 8 },
  };


  const scatterDatasets = (candidates || []).map((c, idx) => {
    const color = COLORS[idx % COLORS.length];
    const semanticPct = Math.round((c.semantic || 0) * 100);
    const skillPct = Math.round((c.skill_score || 0) * 100);
    const size = Math.max(6, Math.min(12, 6 + Math.round((c.score || 0) * 6)));
    return {
      label: c.candidate_name || `Cand ${c.candidate_id}`,
      data: [{ x: semanticPct, y: skillPct }],
      backgroundColor: color,
      pointRadius: size,
      pointHoverRadius: size + 3,
    };
  });

  const scatterData = { datasets: scatterDatasets };
  const scatterOptions = {
    maintainAspectRatio: false,
    responsive: true,
    scales: {
      x: { title: { display: true, text: "Semantic (%)" }, min: 0, max: 100 },
      y: { title: { display: true, text: "Skill-match (%)" }, min: 0, max: 100 },
    },
  };


  const lineDatasets = (candidates || []).map((cand, idx) => {
    const color = COLORS[idx % COLORS.length];
    const data = (cand.coverage_vector || []).map((v) => (v ? 1 : 0));
    return {
      label: cand.candidate_name || `Candidate ${cand.candidate_id}`,
      data,
      borderColor: color,
      borderWidth: 2,
      tension: 0.25, // smooth curve
      showLine: true,
      fill: false,
      pointStyle: function (ctx) {
        const v = ctx.raw;
        return v === 1 ? tickImg : crossImg; // ✓ if skill matched, ✕ if missing
      },
      pointRadius: 10,
      pointHoverRadius: 12,
    };
  });

  const lineData = { labels: skillLabels, datasets: lineDatasets };
  const lineOptions = {
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
  };


  return (
    <div style={{ display: "grid", gap: 12 }}>
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "1fr 400px",
          gap: 12,
          alignItems: "start",
        }}
      >
        {/* LEFT COLUMN → BAR CHART */}
        <div
          style={{
            background: "#fff",
            padding: 14,
            borderRadius: 8,
            height: 340,
          }}
        >
          <h4 style={{ marginTop: 0 }}>Job Skill Coverage</h4>
          <div style={{ height: "280px" }}>
            {skillLabels.length ? (
              <Bar data={barData} options={barOptions} />
            ) : (
              <div style={{ color: "#666" }}>No job skills defined.</div>
            )}
          </div>
        </div>

        {/* RIGHT COLUMN → DONUT + SCATTER */}
        <div style={{ display: "grid", gridTemplateRows: "220px 260px", gap: 12 }}>
          {/* Donut Chart */}
          <div style={{ background: "#fff", padding: 12, borderRadius: 8 }}>
            <h4 style={{ marginTop: 0 }}>Candidate Quality</h4>
            <div style={{ width: "100%", height: 150 }}>
              <Doughnut data={donutData} options={donutOptions} />
            </div>
          </div>

          {/* Scatter Chart */}
          <div style={{ background: "#fff", padding: 12, borderRadius: 8 }}>
            <h4 style={{ marginTop: 0 }}>Semantic vs Skill-match</h4>
            <div style={{ height: 200 }}>
              <Scatter data={scatterData} options={scatterOptions} />
            </div>
          </div>
        </div>
      </div>

      {/* BOTTOM SECTION → LINE CHART */}
      <div style={{ background: "#fff", padding: 12, borderRadius: 8, minHeight: 200 }}>
        <h4 style={{ marginTop: 0 }}>Skill Presence Lines</h4>
        <div style={{ color: "#666", marginBottom: 8, fontSize: 13 }}>
          Each colored line = a candidate. Hover points to see details (✓ matched, ✕ missing).
        </div>

        {skillLabels.length && candidates.length ? (
          <div style={{ height: 300 }}>
            <Line data={lineData} options={lineOptions} />
          </div>
        ) : (
          <div style={{ color: "#666" }}>No skill vector data available.</div>
        )}
      </div>
    </div>
  );
}


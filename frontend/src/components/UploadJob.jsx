import React, { useState } from "react";
import api from "../api";
import { toast } from "react-toastify";
import { useNavigate } from "react-router-dom";

export default function UploadJob() {
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [skillsText, setSkillsText] = useState("");
  const [skillList, setSkillList] = useState(["python", "sql", "fastapi", "docker"]);
  const [loading, setLoading] = useState(false);
  const navigate = useNavigate();

  const handleAddSkill = (e) => {
    if (e.key === "Enter" || e.key === ",") {
      e.preventDefault();
      const val = skillsText.trim().toLowerCase().replace(/[^a-z0-9\+\#\.\-\s]/g, "");
      if (val && !skillList.includes(val)) {
        setSkillList([...skillList, val]);
      }
      setSkillsText("");
    }
  };

  const removeSkill = (skillToRemove) => {
    setSkillList(skillList.filter((s) => s !== skillToRemove));
  };

  async function handleSubmit(e) {
    e.preventDefault();

    const cleanTitle = title.trim();
    const cleanDesc = description.trim();

    if (cleanTitle.length < 3 || cleanTitle.length > 120) {
      toast.warn("⚠️ Job title must be between 3 and 120 characters.");
      return;
    }

    if (cleanDesc.length < 20) {
      toast.warn("⚠️ Job description must be at least 20 characters describing requirements.");
      return;
    }

    // Merge any remaining input in skillsText
    let finalSkills = [...skillList];
    if (skillsText.trim()) {
      const extra = skillsText
        .split(",")
        .map((s) => s.trim().toLowerCase().replace(/[^a-z0-9\+\#\.\-\s]/g, ""))
        .filter(Boolean);
      finalSkills = Array.from(new Set([...finalSkills, ...extra]));
    }

    if (finalSkills.length === 0) {
      toast.warn("⚠️ Please specify at least one required skill (e.g. Python, Docker).");
      return;
    }

    const raw_user_id = localStorage.getItem("user_id");
    const role = (localStorage.getItem("role") || "").toLowerCase().trim();
    const user_id = Number(raw_user_id);

    if (!raw_user_id || isNaN(user_id) || user_id <= 0) {
      toast.error("❌ Session expired. Please login again.");
      localStorage.clear();
      navigate("/");
      return;
    }

    if (role !== "hr") {
      toast.error("❌ Access restricted: Only HR recruiters can create job postings.");
      navigate("/");
      return;
    }

    const fd = new FormData();
    fd.append("title", cleanTitle);
    fd.append("description", cleanDesc);
    fd.append("skills", finalSkills.join(","));
    fd.append("created_by", String(user_id));

    try {
      setLoading(true);
      const res = await api.post("/api/jobs", fd);
      const jobId = res?.data?.job_id;

      toast.success(`✅ Job requisition published successfully! (Requisition ID: #${jobId})`);

      if (jobId) {
        navigate(`/upload-resume?jobId=${jobId}`);
      } else {
        navigate("/");
      }
    } catch (err) {
      console.error("Create job error", err);
      const detail = err?.response?.data?.detail || err?.message || "Failed to create job";
      toast.error(`❌ ${detail}`);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div style={{ padding: 24, maxWidth: 840, margin: "0 auto" }}>
      <div className="card" style={{ boxShadow: "0 10px 30px rgba(0,0,0,0.06)", borderRadius: 16 }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 20 }}>
          <div>
            <h2 style={{ margin: "0 0 4px 0", fontSize: 22, color: "#0f172a", fontWeight: 800 }}>
              ➕ Create Job Requisition
            </h2>
            <p style={{ margin: 0, fontSize: 13, color: "#64748b" }}>
              Publish open vacancies with target skill profiles for automated AI candidate screening
            </p>
          </div>
          <button onClick={() => navigate("/")} className="btn ghost" style={{ padding: "8px 14px" }}>
            ← Back to Dashboard
          </button>
        </div>

        <form onSubmit={handleSubmit} style={{ display: "grid", gap: 18 }}>
          <div>
            <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 4 }}>
              <label className="small" style={{ fontWeight: 700, color: "#1e293b" }}>
                Job Title *
              </label>
              <span className="small" style={{ color: title.length > 120 ? "#ef4444" : "#64748b" }}>
                {title.length}/120 characters (min 3)
              </span>
            </div>
            <input
              className="input"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="e.g. Senior Machine Learning & Backend Engineer"
              maxLength={120}
              required
            />
          </div>

          <div>
            <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 4 }}>
              <label className="small" style={{ fontWeight: 700, color: "#1e293b" }}>
                Job Description & Scope *
              </label>
              <span className="small" style={{ color: description.length < 20 ? "#f59e0b" : "#10b981" }}>
                {description.length}/10,000 chars (min 20)
              </span>
            </div>
            <textarea
              className="input"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              rows={6}
              placeholder="Provide role overview, core responsibilities, qualifications, and tech stack details..."
              required
            />
          </div>

          <div>
            <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 4 }}>
              <label className="small" style={{ fontWeight: 700, color: "#1e293b" }}>
                Target Required Skills ({skillList.length} defined) *
              </label>
              <span className="small" style={{ color: "#64748b" }}>
                Press Enter or Comma to add tags
              </span>
            </div>

            {/* Interactive Skill Chips */}
            <div style={{ display: "flex", flexWrap: "wrap", gap: 6, marginBottom: 8 }}>
              {skillList.map((skill) => (
                <span
                  key={skill}
                  style={{
                    display: "inline-flex",
                    alignItems: "center",
                    gap: 6,
                    background: "#eff6ff",
                    color: "#1d4ed8",
                    border: "1px solid #bfdbfe",
                    padding: "4px 10px",
                    borderRadius: 20,
                    fontSize: 12,
                    fontWeight: 700
                  }}
                >
                  {skill}
                  <button
                    type="button"
                    onClick={() => removeSkill(skill)}
                    style={{
                      background: "transparent",
                      border: "none",
                      color: "#ef4444",
                      cursor: "pointer",
                      fontWeight: 900,
                      padding: 0,
                      lineHeight: 1
                    }}
                  >
                    ×
                  </button>
                </span>
              ))}
            </div>

            <input
              className="input"
              value={skillsText}
              onChange={(e) => setSkillsText(e.target.value)}
              onKeyDown={handleAddSkill}
              placeholder="Type skill name and press Enter (e.g. pytorch, redis, kubernetes)"
            />
            <span className="small" style={{ color: "#64748b", marginTop: 4, display: "block" }}>
              💡 Skills will be used for exact keyword overlap and vector coverage radar charts.
            </span>
          </div>

          <div className="button-row" style={{ marginTop: 10, display: "flex", gap: 12 }}>
            <button
              type="submit"
              disabled={loading || title.trim().length < 3 || description.trim().length < 20}
              className="btn"
              style={{
                padding: "12px 24px",
                background: loading ? "#94a3b8" : "linear-gradient(135deg, #2563eb 0%, #1d4ed8 100%)"
              }}
            >
              {loading ? "Publishing Requisition..." : "🚀 Publish Requisition & Ingest Resumes"}
            </button>

            <button
              type="button"
              className="btn secondary"
              onClick={() => {
                setTitle("");
                setDescription("");
                setSkillsText("");
                setSkillList(["python", "sql", "fastapi"]);
              }}
            >
              Reset Form
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
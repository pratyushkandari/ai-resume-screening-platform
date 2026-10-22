import { useState } from "react";
import api, { getErrorMessage } from "../api";
import { toast } from "react-toastify";
import { useNavigate } from "react-router-dom";

/**
 * "Post a New Position" form for recruiters. Skills are added as tags (Enter or
 * comma) and sent as one comma-separated field; the API normalises them. After
 * publishing, the dashboard opens with the new job selected.
 */
export default function UploadJob() {
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [skillsText, setSkillsText] = useState("");
  const [skillList, setSkillList] = useState([]);
  const [loading, setLoading] = useState(false);
  const navigate = useNavigate();

  const handleAddSkill = (e) => {
    if (e.key === "Enter" || e.key === ",") {
      e.preventDefault();
      const val = skillsText.trim().toLowerCase().replace(/[^a-z0-9+#./\-\s]/g, "");
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
      toast.warn("Job title must be between 3 and 120 characters.");
      return;
    }

    if (cleanDesc.length < 20) {
      toast.warn("Job description must be at least 20 characters describing requirements.");
      return;
    }

    let finalSkills = [...skillList];
    if (skillsText.trim()) {
      const extra = skillsText
        .split(",")
        .map((s) => s.trim().toLowerCase().replace(/[^a-z0-9+#./\-\s]/g, ""))
        .filter(Boolean);
      finalSkills = Array.from(new Set([...finalSkills, ...extra]));
    }

    if (finalSkills.length === 0) {
      toast.warn("Please specify at least one required skill (e.g. Python, Docker).");
      return;
    }

    const fd = new FormData();
    fd.append("title", cleanTitle);
    fd.append("description", cleanDesc);
    fd.append("skills", finalSkills.join(","));

    try {
      setLoading(true);
      const res = await api.post("/api/jobs", fd);
      const jobId = res?.data?.job_id;

      toast.success(`Position published successfully (REQ-#${jobId})`);
      navigate("/", { state: { selectedJobId: jobId } });
    } catch (err) {
      toast.error(getErrorMessage(err, "Failed to create the job requisition."));
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="page" style={{ padding: "28px 32px", maxWidth: 840, margin: "0 auto" }}>
      <div className="card" style={{ padding: 28 }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 24 }}>
          <div>
            <h2 style={{ margin: 0, fontSize: 22, color: "#0f172a", fontWeight: 800 }}>
              Post a New Position
            </h2>
            <p style={{ margin: "4px 0 0 0", fontSize: 13, color: "#64748b" }}>
              Define position requirements and required technical competencies for candidate evaluation.
            </p>
          </div>
          <button onClick={() => navigate("/")} className="btn btn-ghost" style={{ fontSize: 13 }}>
            ← Back to Dashboard
          </button>
        </div>

        <form onSubmit={handleSubmit} style={{ display: "grid", gap: 18 }}>
          <div>
            <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 4 }}>
              <label htmlFor="job-title" className="input-label" style={{ margin: 0 }}>
                Job Title *
              </label>
              <span style={{ fontSize: 12, color: title.length > 120 ? "#dc2626" : "#64748b" }}>
                {title.length}/120 characters
              </span>
            </div>
            <input
              id="job-title"
              className="input"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="e.g. Senior Machine Learning Engineer"
              maxLength={120}
              required
            />
          </div>

          <div>
            <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 4 }}>
              <label htmlFor="job-description" className="input-label" style={{ margin: 0 }}>
                Job Description & Scope *
              </label>
              <span style={{ fontSize: 12, color: description.length < 20 ? "#b45309" : "#047857" }}>
                {description.length} chars (min 20)
              </span>
            </div>
            <textarea
              id="job-description"
              className="input"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              rows={6}
              placeholder="Outline the core responsibilities, qualifications, and target technical domain..."
              required
            />
          </div>

          <div>
            <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 4 }}>
              <label htmlFor="job-skill-input" className="input-label" style={{ margin: 0 }}>
                Required Technical Competencies ({skillList.length}) *
              </label>
              <span style={{ fontSize: 12, color: "#64748b" }}>
                Press Enter or Comma to add tags
              </span>
            </div>

            {/* Skill Tags */}
            <div style={{ display: "flex", flexWrap: "wrap", gap: 6, marginBottom: 8 }}>
              {skillList.map((skill) => (
                <span
                  key={skill}
                  style={{
                    display: "inline-flex",
                    alignItems: "center",
                    gap: 6,
                    backgroundColor: "#eff6ff",
                    color: "#1d4ed8",
                    border: "1px solid #bfdbfe",
                    padding: "4px 10px",
                    borderRadius: 20,
                    fontSize: 12,
                    fontWeight: 600
                  }}
                >
                  {skill}
                  <button
                    type="button"
                    aria-label={`Remove ${skill}`}
                    onClick={() => removeSkill(skill)}
                    style={{
                      background: "transparent",
                      border: "none",
                      color: "#1d4ed8",
                      cursor: "pointer",
                      fontWeight: 700,
                      padding: 0,
                      lineHeight: 1
                    }}
                    onMouseOver={(e) => (e.currentTarget.style.color = "#dc2626")}
                    onMouseOut={(e) => (e.currentTarget.style.color = "#1d4ed8")}
                  >
                    ×
                  </button>
                </span>
              ))}
            </div>

            <input
              id="job-skill-input"
              className="input"
              value={skillsText}
              onChange={(e) => setSkillsText(e.target.value)}
              onKeyDown={handleAddSkill}
              placeholder="Type competency and press Enter (e.g. PyTorch, Redis, Kubernetes)"
            />
            <span style={{ fontSize: 12, color: "#64748b", marginTop: 4, display: "block" }}>
              Skills are matched against the text of each resume (70% of the score); the title and description drive the semantic similarity (30%).
            </span>
          </div>

          <div style={{ marginTop: 10, display: "flex", gap: 12 }}>
            <button
              type="submit"
              disabled={loading || title.trim().length < 3 || description.trim().length < 20}
              className="btn btn-primary"
              style={{ padding: "11px 24px", fontSize: 14 }}
            >
              {loading ? "Publishing Position..." : "Publish Position"}
            </button>

            <button
              type="button"
              className="btn btn-secondary"
              onClick={() => {
                setTitle("");
                setDescription("");
                setSkillsText("");
                setSkillList([]);
              }}
            >
              Reset
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
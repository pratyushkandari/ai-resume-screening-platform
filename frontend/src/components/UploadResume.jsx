import React, { useEffect, useState, useRef } from "react";
import api from "../api";
import { toast } from "react-toastify";
import { useNavigate, useLocation } from "react-router-dom";

const MAX_FILE_SIZE_BYTES = 15 * 1024 * 1024; // 15MB
const ALLOWED_EXTS = [".pdf", ".docx", ".doc", ".txt"];

export default function UploadResume() {
  const navigate = useNavigate();
  const location = useLocation();
  const fileInputRef = useRef(null);

  const [jobs, setJobs] = useState([]);
  const [jobId, setJobId] = useState("");
  const [selectedFiles, setSelectedFiles] = useState([]);
  const [fileErrors, setFileErrors] = useState([]);
  const [uploading, setUploading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [uploadResult, setUploadResult] = useState(null);

  useEffect(() => {
    loadJobs();
  }, []);

  async function loadJobs() {
    try {
      const res = await api.get("/api/jobs", { params: { role: "candidate" } });
      const jobList = res.data || [];
      setJobs(jobList);

      const params = new URLSearchParams(location.search);
      const paramJobId = params.get("jobId");
      if (paramJobId) {
        setJobId(paramJobId);
      } else if (jobList.length > 0) {
        setJobId(String(jobList[0].job_id));
      }
    } catch (e) {
      toast.error("Failed to load active job vacancies.");
    }
  }

  function validateAndSetFiles(filesArray) {
    const valid = [];
    const errors = [];

    filesArray.forEach((file) => {
      const ext = "." + file.name.split(".").pop().toLowerCase();
      if (!ALLOWED_EXTS.includes(ext)) {
        errors.push(`'${file.name}' rejected: Unsupported extension (${ext}). Allowed: .pdf, .docx, .doc, .txt`);
      } else if (file.size > MAX_FILE_SIZE_BYTES) {
        errors.push(`'${file.name}' rejected: Exceeds 15MB size limit (${(file.size / (1024 * 1024)).toFixed(1)}MB).`);
      } else if (file.size === 0) {
        errors.push(`'${file.name}' rejected: File is empty (0 bytes).`);
      } else {
        valid.push(file);
      }
    });

    if (errors.length > 0) {
      setFileErrors(errors);
      toast.warn(`⚠️ ${errors.length} file(s) failed validation.`);
    } else {
      setFileErrors([]);
    }

    setSelectedFiles(valid);
    setUploadResult(null);
  }

  function handleFileChange(e) {
    if (e.target.files) {
      validateAndSetFiles(Array.from(e.target.files));
    }
  }

  function handleDrop(e) {
    e.preventDefault();
    if (e.dataTransfer.files) {
      validateAndSetFiles(Array.from(e.dataTransfer.files));
    }
  }

  async function submitBatch() {
    if (selectedFiles.length === 0) {
      toast.warn("⚠️ Please select one or more valid resume files (.pdf, .docx, .txt)");
      return;
    }

    setUploading(true);
    setUploadProgress(15);

    try {
      const fd = new FormData();
      if (jobId) {
        fd.append("job_id", jobId);
      }

      if (selectedFiles.length === 1) {
        fd.append("file", selectedFiles[0]);
        setUploadProgress(50);
        const res = await api.post("/api/resumes/upload", fd);
        setUploadProgress(100);
        toast.success("✅ Resume uploaded, parsed, and vectorized successfully!");
        setUploadResult({
          total_files: 1,
          successful: 1,
          results: [{ filename: selectedFiles[0].name, status: "processed" }]
        });
      } else {
        selectedFiles.forEach((file) => {
          fd.append("files", file);
        });
        setUploadProgress(45);
        const res = await api.post("/api/resumes/batch-upload", fd);
        setUploadProgress(100);
        toast.success(`🎉 Batch complete: ${res.data?.successful || 0} / ${res.data?.total_files || 0} resumes indexed!`);
        setUploadResult(res.data);
      }

      setSelectedFiles([]);
      if (fileInputRef.current) fileInputRef.current.value = "";
    } catch (e) {
      const errorDetail = e.response?.data?.detail || "Document upload processing failed.";
      toast.error(`❌ ${errorDetail}`);
    } finally {
      setUploading(false);
    }
  }

  return (
    <div style={{ padding: 24, maxWidth: 880, margin: "0 auto" }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 20 }}>
        <div>
          <h1 style={{ margin: 0, fontSize: 24, color: "#0f172a", fontWeight: "800" }}>
            📤 Enterprise Resume Ingestion Pipeline
          </h1>
          <p style={{ margin: "4px 0 0 0", color: "#64748b", fontSize: 14 }}>
            Multi-threaded text extraction, contact parsing, and dense semantic embedding generation
          </p>
        </div>

        <button
          onClick={() => navigate("/", { state: { selectedJobId: jobId ? Number(jobId) : undefined } })}
          className="btn secondary"
          style={{ fontSize: 13 }}
        >
          ← Back to Dashboard
        </button>
      </div>

      <div className="card" style={{ padding: 28, borderRadius: 16, boxShadow: "0 10px 30px rgba(0,0,0,0.06)" }}>
        {/* Job Selector */}
        <div style={{ marginBottom: 20 }}>
          <label style={{ display: "block", fontWeight: 700, fontSize: 14, color: "#334155", marginBottom: 6 }}>
            🎯 Target Job Requisition Opening
          </label>
          <select
            value={jobId}
            onChange={(e) => setJobId(e.target.value)}
            style={{
              width: "100%",
              padding: "10px 14px",
              borderRadius: 8,
              border: "1px solid #cbd5e1",
              fontWeight: 600,
              fontSize: 14,
              background: "#fff"
            }}
          >
            <option value="">-- General Talent Pool (Unassigned) --</option>
            {jobs.map((j) => (
              <option key={j.job_id} value={j.job_id}>
                #{j.job_id} — {j.title}
              </option>
            ))}
          </select>
        </div>

        {/* Drag & Drop Upload Zone */}
        <div
          onDragOver={(e) => e.preventDefault()}
          onDrop={handleDrop}
          onClick={() => fileInputRef.current?.click()}
          style={{
            border: "2px dashed #3b82f6",
            borderRadius: 14,
            padding: "40px 20px",
            textAlign: "center",
            background: "#f8fafc",
            cursor: "pointer",
            transition: "all 0.2s"
          }}
        >
          <input
            ref={fileInputRef}
            type="file"
            multiple
            accept=".pdf,.docx,.doc,.txt"
            onChange={handleFileChange}
            style={{ display: "none" }}
          />

          <div style={{ fontSize: 44 }}>📁</div>
          <h3 style={{ margin: "10px 0 4px 0", color: "#1e293b", fontSize: 18, fontWeight: 700 }}>
            Click or Drag & Drop Resume Documents Here
          </h3>
          <p style={{ margin: 0, color: "#64748b", fontSize: 13 }}>
            Supported formats: <strong>.PDF, .DOCX, .DOC, .TXT</strong> (Max 15MB per document)
          </p>
        </div>

        {/* File Validation Warnings */}
        {fileErrors.length > 0 && (
          <div style={{ marginTop: 14, padding: 12, background: "#fee2e2", borderRadius: 8, border: "1px solid #fca5a5" }}>
            <div style={{ fontWeight: 700, color: "#991b1b", fontSize: 13, marginBottom: 4 }}>
              ⚠️ File Validation Issues ({fileErrors.length}):
            </div>
            {fileErrors.map((err, i) => (
              <div key={i} style={{ fontSize: 12, color: "#b91c1c", marginTop: 2 }}>
                • {err}
              </div>
            ))}
          </div>
        )}

        {/* Valid Files Selected List */}
        {selectedFiles.length > 0 && (
          <div style={{ marginTop: 18 }}>
            <div style={{ fontWeight: 700, fontSize: 14, color: "#0f172a", marginBottom: 8 }}>
              Valid Resumes Ready for Ingestion ({selectedFiles.length} file{selectedFiles.length > 1 ? "s" : ""}):
            </div>
            <div
              style={{
                maxHeight: 160,
                overflowY: "auto",
                background: "#f1f5f9",
                borderRadius: 8,
                padding: 10,
                display: "grid",
                gap: 6
              }}
            >
              {selectedFiles.map((f, idx) => (
                <div
                  key={idx}
                  style={{
                    display: "flex",
                    justifyContent: "space-between",
                    fontSize: 13,
                    background: "#fff",
                    padding: "6px 10px",
                    borderRadius: 6,
                    border: "1px solid #e2e8f0"
                  }}
                >
                  <span style={{ fontWeight: 600, color: "#334155" }}>📄 {f.name}</span>
                  <span style={{ color: "#64748b", fontWeight: 500 }}>{(f.size / 1024).toFixed(1)} KB</span>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Progress Bar */}
        {uploading && (
          <div style={{ marginTop: 18 }}>
            <div style={{ display: "flex", justifyContent: "space-between", fontSize: 12, marginBottom: 4, fontWeight: 600 }}>
              <span>Extracting text, contacts, and dense embeddings...</span>
              <span>{uploadProgress}%</span>
            </div>
            <div style={{ width: "100%", height: 8, background: "#e2e8f0", borderRadius: 4, overflow: "hidden" }}>
              <div
                style={{
                  width: `${uploadProgress}%`,
                  height: "100%",
                  background: "linear-gradient(90deg, #2563eb, #3b82f6)",
                  transition: "width 0.3s"
                }}
              />
            </div>
          </div>
        )}

        {/* Action Button */}
        <button
          onClick={submitBatch}
          disabled={uploading || selectedFiles.length === 0}
          style={{
            marginTop: 20,
            width: "100%",
            padding: "13px",
            borderRadius: 10,
            border: "none",
            background: selectedFiles.length === 0 ? "#cbd5e1" : "linear-gradient(135deg, #2563eb 0%, #1d4ed8 100%)",
            color: "#fff",
            fontWeight: "700",
            fontSize: "15px",
            cursor: selectedFiles.length === 0 || uploading ? "not-allowed" : "pointer",
            boxShadow: "0 4px 14px rgba(37,99,235,0.25)",
            transition: "all 0.2s"
          }}
        >
          {uploading
            ? "⚡ Processing Multi-Threaded Ingestion..."
            : `🚀 Ingest & Index ${selectedFiles.length > 0 ? `(${selectedFiles.length} Documents)` : "Documents"}`}
        </button>

        {/* Ingestion Results Card */}
        {uploadResult && (
          <div
            style={{
              marginTop: 20,
              padding: 16,
              background: "#f0fdf4",
              border: "1px solid #bbf7d0",
              borderRadius: 12
            }}
          >
            <div style={{ fontWeight: 800, color: "#166534", fontSize: 16, marginBottom: 6 }}>
              ✅ Ingestion & Feature Extraction Succeeded!
            </div>
            <div style={{ fontSize: 13, color: "#15803d" }}>
              Successfully indexed <strong>{uploadResult.successful}</strong> / <strong>{uploadResult.total_files}</strong> resume documents into candidate talent pool.
            </div>

            <div style={{ marginTop: 14, display: "flex", gap: 10 }}>
              <button
                onClick={() => navigate("/", { state: { selectedJobId: jobId ? Number(jobId) : undefined } })}
                className="btn"
                style={{ fontSize: 13, padding: "8px 18px" }}
              >
                📊 Open Recruiter Dashboard & Rankings
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

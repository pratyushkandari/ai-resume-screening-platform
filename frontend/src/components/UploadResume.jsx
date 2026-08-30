import React, { useEffect, useState, useRef } from "react";
import api from "../api";
import { toast } from "react-toastify";
import { useNavigate, useLocation } from "react-router-dom";

const MAX_FILE_SIZE_BYTES = 15 * 1024 * 1024; // 15MB
const ALLOWED_EXTS = [".pdf", ".docx", ".doc", ".txt"];

export default function UploadResume({ preselectedJobId }) {
  const navigate = useNavigate();
  const location = useLocation();
  const fileInputRef = useRef(null);

  const [jobs, setJobs] = useState([]);
  const [jobId, setJobId] = useState(preselectedJobId || "");
  const [selectedFiles, setSelectedFiles] = useState([]);
  const [fileErrors, setFileErrors] = useState([]);
  const [uploading, setUploading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [uploadResult, setUploadResult] = useState(null);

  useEffect(() => {
    loadJobs();
  }, []);

  useEffect(() => {
    if (preselectedJobId) {
      setJobId(String(preselectedJobId));
    }
  }, [preselectedJobId]);

  async function loadJobs() {
    try {
      const res = await api.get("/api/jobs", { params: { role: "candidate" } });
      const jobList = res.data || [];
      setJobs(jobList);

      const params = new URLSearchParams(location.search);
      const paramJobId = params.get("jobId");
      if (paramJobId) {
        setJobId(paramJobId);
      } else if (!jobId && jobList.length > 0 && !preselectedJobId) {
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
        errors.push(`'${file.name}' rejected: Unsupported file format (${ext}). Allowed: .pdf, .docx, .doc, .txt`);
      } else if (file.size > MAX_FILE_SIZE_BYTES) {
        errors.push(`'${file.name}' rejected: Exceeds 15MB limit (${(file.size / (1024 * 1024)).toFixed(1)}MB).`);
      } else if (file.size === 0) {
        errors.push(`'${file.name}' rejected: File is empty.`);
      } else {
        valid.push(file);
      }
    });

    if (errors.length > 0) {
      setFileErrors(errors);
      toast.warn(`${errors.length} file(s) failed validation.`);
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
      toast.warn("Please select a resume file (.pdf, .docx, or .txt)");
      return;
    }

    setUploading(true);
    setUploadProgress(20);

    try {
      const fd = new FormData();
      if (jobId) {
        fd.append("job_id", jobId);
      }

      if (selectedFiles.length === 1) {
        fd.append("file", selectedFiles[0]);
        setUploadProgress(60);
        const res = await api.post("/api/resumes/upload", fd);
        setUploadProgress(100);
        toast.success("Application and resume submitted successfully!");
        setUploadResult({
          total_files: 1,
          successful: 1,
          results: [{ filename: selectedFiles[0].name, status: "processed" }]
        });
      } else {
        selectedFiles.forEach((file) => {
          fd.append("files", file);
        });
        setUploadProgress(50);
        const res = await api.post("/api/resumes/batch-upload", fd);
        setUploadProgress(100);
        toast.success(`Batch submission complete: ${res.data?.successful || 0} resumes processed.`);
        setUploadResult(res.data);
      }

      setSelectedFiles([]);
      if (fileInputRef.current) fileInputRef.current.value = "";
    } catch (e) {
      const errorDetail = e.response?.data?.detail || "Resume upload processing failed.";
      toast.error(errorDetail);
    } finally {
      setUploading(false);
    }
  }

  return (
    <div style={{ maxWidth: 880, margin: "0 auto" }}>
      <div className="card" style={{ padding: 28 }}>
        <div style={{ marginBottom: 20 }}>
          <h2 style={{ fontSize: 20, fontWeight: 700, color: "#0f172a", margin: 0 }}>
            Submit Your Application
          </h2>
          <p style={{ margin: "4px 0 0 0", color: "#64748b", fontSize: 13 }}>
            Upload your resume (.PDF, .DOCX, .TXT) to match with active position requirements.
          </p>
        </div>

        {/* Position Selector */}
        <div style={{ marginBottom: 20 }}>
          <label className="input-label">Target Position</label>
          <select
            value={jobId}
            onChange={(e) => setJobId(e.target.value)}
            style={{ fontSize: 14 }}
          >
            <option value="">-- General Talent Pool (Unassigned) --</option>
            {jobs.map((j) => (
              <option key={j.job_id} value={j.job_id}>
                REQ-{j.job_id}: {j.title}
              </option>
            ))}
          </select>
        </div>

        {/* Upload Zone */}
        <div
          onDragOver={(e) => e.preventDefault()}
          onDrop={handleDrop}
          onClick={() => fileInputRef.current?.click()}
          style={{
            border: "2px dashed #cbd5e1",
            borderRadius: 12,
            padding: "36px 20px",
            textAlign: "center",
            backgroundColor: "#f8fafc",
            cursor: "pointer",
            transition: "all 0.15s ease"
          }}
          onMouseOver={(e) => (e.currentTarget.style.borderColor = "#3b82f6")}
          onMouseOut={(e) => (e.currentTarget.style.borderColor = "#cbd5e1")}
        >
          <input
            ref={fileInputRef}
            type="file"
            multiple
            accept=".pdf,.docx,.doc,.txt"
            onChange={handleFileChange}
            style={{ display: "none" }}
          />

          <div
            style={{
              width: 44,
              height: 44,
              borderRadius: "50%",
              backgroundColor: "#eff6ff",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              margin: "0 auto 12px auto",
              color: "#2563eb"
            }}
          >
            <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>
              <polyline points="17 8 12 3 7 8"/>
              <line x1="12" x2="12" y1="3" y2="15"/>
            </svg>
          </div>

          <div style={{ fontWeight: 600, color: "#1e293b", fontSize: 15, marginBottom: 4 }}>
            Click or drag & drop your resume here
          </div>
          <p style={{ margin: 0, color: "#64748b", fontSize: 13 }}>
            Supported formats: <strong>PDF, DOCX, DOC, TXT</strong> (Up to 15MB)
          </p>
        </div>

        {/* Validation Errors */}
        {fileErrors.length > 0 && (
          <div style={{ marginTop: 14, padding: 12, backgroundColor: "#fff1f2", borderRadius: 8, border: "1px solid #fecdd3" }}>
            <div style={{ fontWeight: 600, color: "#be123c", fontSize: 13, marginBottom: 4 }}>
              File Validation Notices:
            </div>
            {fileErrors.map((err, i) => (
              <div key={i} style={{ fontSize: 12, color: "#9f1239", marginTop: 2 }}>
                • {err}
              </div>
            ))}
          </div>
        )}

        {/* Selected Files List */}
        {selectedFiles.length > 0 && (
          <div style={{ marginTop: 16 }}>
            <div style={{ fontSize: 13, fontWeight: 600, color: "#334155", marginBottom: 8 }}>
              Selected Files ({selectedFiles.length}):
            </div>
            <div style={{ display: "grid", gap: 6 }}>
              {selectedFiles.map((f, idx) => (
                <div
                  key={idx}
                  style={{
                    display: "flex",
                    justifyContent: "space-between",
                    alignItems: "center",
                    padding: "8px 12px",
                    backgroundColor: "#f8fafc",
                    borderRadius: 6,
                    border: "1px solid #e2e8f0",
                    fontSize: 13
                  }}
                >
                  <span style={{ fontWeight: 500, color: "#0f172a" }}>{f.name}</span>
                  <span style={{ color: "#64748b", fontSize: 12 }}>{(f.size / 1024).toFixed(1)} KB</span>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Progress Bar */}
        {uploading && (
          <div style={{ marginTop: 16 }}>
            <div style={{ display: "flex", justifyContent: "space-between", fontSize: 12, fontWeight: 600, color: "#475569", marginBottom: 4 }}>
              <span>Analyzing resume and vectorizing competencies...</span>
              <span>{uploadProgress}%</span>
            </div>
            <div style={{ height: 6, width: "100%", backgroundColor: "#e2e8f0", borderRadius: 3, overflow: "hidden" }}>
              <div
                style={{
                  height: "100%",
                  width: `${uploadProgress}%`,
                  backgroundColor: "#2563eb",
                  transition: "width 0.3s ease"
                }}
              />
            </div>
          </div>
        )}

        {/* Submit Button */}
        <button
          onClick={submitBatch}
          disabled={uploading || selectedFiles.length === 0}
          className="btn btn-primary"
          style={{
            width: "100%",
            marginTop: 20,
            padding: "12px",
            fontSize: 14,
            fontWeight: 700
          }}
        >
          {uploading ? "Submitting Application..." : "Submit Application"}
        </button>

        {/* Success Confirmation */}
        {uploadResult && (
          <div
            style={{
              marginTop: 18,
              padding: 16,
              backgroundColor: "#ecfdf5",
              border: "1px solid #a7f3d0",
              borderRadius: 8
            }}
          >
            <div style={{ fontWeight: 700, color: "#047857", fontSize: 14, marginBottom: 4 }}>
              Application Successfully Submitted
            </div>
            <div style={{ fontSize: 13, color: "#065f46" }}>
              Your resume has been indexed and submitted for review against the selected position.
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

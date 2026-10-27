import { useEffect, useRef, useState } from "react";
import api, { getErrorMessage } from "../api";
import { toast } from "react-toastify";
import useUpload from "../hooks/useUpload";

const MAX_FILE_SIZE_BYTES = 15 * 1024 * 1024; // must match MAX_UPLOAD_MB on the server
const MAX_FILES = 25; // must match MAX_BATCH_FILES on the server
const ALLOWED_EXTS = [".pdf", ".docx", ".txt"];

/**
 * Resume submission form. `jobs` can be passed in by a parent that already
 * loaded them (CandidatePage); otherwise they are fetched here.
 */
export default function UploadResume({ preselectedJobId, jobs: jobsProp }) {
  const fileInputRef = useRef(null);
  const { upload, progress, phase, busy } = useUpload();

  const [fetchedJobs, setFetchedJobs] = useState([]);
  const jobs = jobsProp ?? fetchedJobs;
  const [jobId, setJobId] = useState(preselectedJobId ? String(preselectedJobId) : "");
  const [selectedFiles, setSelectedFiles] = useState([]);
  const [fileErrors, setFileErrors] = useState([]);
  const [uploadResult, setUploadResult] = useState(null);

  useEffect(() => {
    if (jobsProp) return;
    api
      .get("/api/jobs")
      .then((res) => setFetchedJobs(res.data || []))
      .catch((err) => toast.error(getErrorMessage(err, "Failed to load open positions.")));
  }, [jobsProp]);

  useEffect(() => {
    if (preselectedJobId) setJobId(String(preselectedJobId));
  }, [preselectedJobId]);

  useEffect(() => {
    if (!jobId && jobs.length > 0) setJobId(String(jobs[0].job_id));
  }, [jobs, jobId]);

  function validateAndSetFiles(filesArray) {
    const valid = [];
    const errors = [];
    filesArray.forEach((file) => {
      const ext = file.name.includes(".") ? "." + file.name.split(".").pop().toLowerCase() : "";
      if (!ALLOWED_EXTS.includes(ext)) {
        errors.push(`'${file.name}': unsupported format${ext ? ` (${ext})` : ""}. Allowed: ${ALLOWED_EXTS.join(", ")}`);
      } else if (file.size > MAX_FILE_SIZE_BYTES) {
        errors.push(`'${file.name}': exceeds the 15 MB limit (${(file.size / (1024 * 1024)).toFixed(1)} MB).`);
      } else if (file.size === 0) {
        errors.push(`'${file.name}': file is empty.`);
      } else {
        valid.push(file);
      }
    });
    if (valid.length > MAX_FILES) {
      errors.push(`Only ${MAX_FILES} files can be submitted at once; the rest were ignored.`);
      valid.length = MAX_FILES;
    }
    setFileErrors(errors);
    if (errors.length) toast.warn(`${errors.length} file(s) were not accepted.`);
    setSelectedFiles(valid);
    setUploadResult(null);
  }

  function handleDrop(e) {
    e.preventDefault();
    if (!busy && e.dataTransfer.files) validateAndSetFiles(Array.from(e.dataTransfer.files));
  }

  function openFilePicker() {
    if (!busy) fileInputRef.current?.click();
  }

  async function submit() {
    if (!jobId) {
      toast.warn("Please choose the position you are applying for.");
      return;
    }
    if (selectedFiles.length === 0) {
      toast.warn("Please select a resume file (.pdf, .docx or .txt).");
      return;
    }
    const fd = new FormData();
    fd.append("job_id", jobId);
    try {
      let result;
      if (selectedFiles.length === 1) {
        fd.append("file", selectedFiles[0]);
        const data = await upload("/api/resumes/upload", fd);
        result = { successful: 1, failed: 0, results: [{ ...data, filename: selectedFiles[0].name }] };
      } else {
        selectedFiles.forEach((file) => fd.append("files", file));
        result = await upload("/api/resumes/batch-upload", fd);
      }
      setUploadResult(result);
      if (result.failed) toast.warn(`${result.successful} processed, ${result.failed} failed.`);
      else toast.success(result.successful === 1 ? "Resume submitted." : `${result.successful} resumes submitted.`);
      setSelectedFiles([]);
      if (fileInputRef.current) fileInputRef.current.value = "";
    } catch (err) {
      toast.error(getErrorMessage(err, "Resume upload failed."));
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
          <label htmlFor="upload-job" className="input-label">Target Position</label>
          <select
            id="upload-job"
            value={jobId}
            onChange={(e) => setJobId(e.target.value)}
            style={{ fontSize: 14 }}
          >
            {jobs.length === 0 && <option value="">No open positions</option>}
            {jobs.map((j) => (
              <option key={j.job_id} value={j.job_id}>
                REQ-{j.job_id}: {j.title}
              </option>
            ))}
          </select>
        </div>

        {/* Upload Zone (inactive while a submission is running: files picked then would be cleared on completion) */}
        <div
          onDragOver={(e) => e.preventDefault()}
          onDrop={handleDrop}
          onClick={openFilePicker}
          onKeyDown={(e) => {
            if (e.key === "Enter" || e.key === " ") {
              e.preventDefault(); // Space would otherwise also scroll the page
              openFilePicker();
            }
          }}
          role="button"
          tabIndex={0}
          aria-label="Choose resume files"
          aria-disabled={busy || undefined}
          style={{
            border: "2px dashed #cbd5e1",
            borderRadius: 12,
            padding: "36px 20px",
            textAlign: "center",
            backgroundColor: "#f8fafc",
            cursor: busy ? "not-allowed" : "pointer",
            opacity: busy ? 0.6 : 1,
            transition: "all 0.15s ease"
          }}
          onMouseOver={(e) => (e.currentTarget.style.borderColor = "#3b82f6")}
          onMouseOut={(e) => (e.currentTarget.style.borderColor = "#cbd5e1")}
        >
          <input
            ref={fileInputRef}
            type="file"
            multiple
            accept=".pdf,.docx,.txt"
            onChange={(e) => e.target.files && validateAndSetFiles(Array.from(e.target.files))}
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
            Supported formats: <strong>PDF, DOCX, TXT</strong> (Up to 15MB)
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
        {busy && (
          <div style={{ marginTop: 16 }} aria-live="polite">
            <div style={{ display: "flex", justifyContent: "space-between", fontSize: 12, fontWeight: 600, color: "#475569", marginBottom: 4 }}>
              <span>{phase === "processing" ? "Uploaded. Extracting text, skills and embeddings..." : "Uploading..."}</span>
              <span>{progress}%</span>
            </div>
            <div style={{ height: 6, width: "100%", backgroundColor: "#e2e8f0", borderRadius: 3, overflow: "hidden" }}>
              <div
                style={{
                  height: "100%",
                  width: `${progress}%`,
                  backgroundColor: "#2563eb",
                  transition: "width 0.3s ease"
                }}
              />
            </div>
          </div>
        )}

        {/* Submit Button */}
        <button
          type="button"
          onClick={submit}
          disabled={busy || selectedFiles.length === 0 || !jobId}
          className="btn btn-primary"
          style={{
            width: "100%",
            marginTop: 20,
            padding: "12px",
            fontSize: 14,
            fontWeight: 700
          }}
        >
          {busy ? "Submitting Application..." : "Submit Application"}
        </button>

        {/* Per-file results */}
        {uploadResult && (
          <div
            role="status"
            style={{
              marginTop: 18,
              padding: 16,
              backgroundColor: uploadResult.failed ? "#fffbeb" : "#ecfdf5",
              border: `1px solid ${uploadResult.failed ? "#fde68a" : "#a7f3d0"}`,
              borderRadius: 8
            }}
          >
            <div style={{ fontWeight: 700, color: uploadResult.failed ? "#92400e" : "#047857", fontSize: 14, marginBottom: 6 }}>
              {uploadResult.failed
                ? `${uploadResult.successful} submitted, ${uploadResult.failed} could not be processed`
                : "Application successfully submitted"}
            </div>
            <ul style={{ margin: 0, paddingLeft: 18, fontSize: 13, color: "#334155" }}>
              {uploadResult.results.map((r, i) => (
                <li key={`${r.filename}-${i}`}>
                  <strong>{r.filename}</strong>:{" "}
                  {r.status === "processed"
                    ? `received${r.parsed?.skills?.length ? ` (skills detected: ${r.parsed.skills.join(", ")})` : ""}`
                    : r.error}
                </li>
              ))}
            </ul>
          </div>
        )}
      </div>
    </div>
  );
}

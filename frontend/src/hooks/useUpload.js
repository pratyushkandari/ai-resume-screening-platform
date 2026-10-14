import { useState, useCallback } from "react";
import api from "../api";
import { toast } from "react-toastify";

/**
 * Custom hook managing asynchronous multipart file uploads and streaming progress.
 *
 * @param {string} endpoint API route for multipart form ingestion
 * @returns {{
 *   uploadFile: (file: File, additionalFields?: Record<string, string>) => Promise<any>,
 *   progress: number,
 *   parsed: any,
 *   loading: boolean,
 *   reset: () => void
 * }}
 */
export default function useUpload(endpoint = "/api/resumes/upload") {
  const [progress, setProgress] = useState(0);
  const [parsed, setParsed] = useState(null);
  const [loading, setLoading] = useState(false);

  const uploadFile = useCallback(async (file, additionalFields = {}) => {
    if (!file) {
      toast.warn("Please select a valid document to upload.");
      return null;
    }

    const formData = new FormData();
    formData.append("file", file);
    Object.entries(additionalFields).forEach(([key, val]) => {
      if (val !== undefined && val !== null) {
        formData.append(key, String(val));
      }
    });

    setLoading(true);
    setProgress(0);

    try {
      const res = await api.post(endpoint, formData, {
        headers: { "Content-Type": "multipart/form-data" },
        onUploadProgress: (ev) => {
          if (ev.total) {
            const pct = Math.round((ev.loaded / ev.total) * 100);
            setProgress(pct);
          }
        },
      });

      const parsedData = res.data?.parsed ?? res.data?.parsed_json ?? null;
      setParsed(parsedData);
      toast.success("Document uploaded and analyzed successfully.");
      return res.data;
    } catch (err) {
      const detail = err.response?.data?.detail || "Upload failed. Please verify file integrity and server status.";
      toast.error(detail);
      return null;
    } finally {
      setLoading(false);
    }
  }, [endpoint]);

  const reset = useCallback(() => {
    setProgress(0);
    setParsed(null);
    setLoading(false);
  }, []);

  return { uploadFile, progress, parsed, loading, reset };
}

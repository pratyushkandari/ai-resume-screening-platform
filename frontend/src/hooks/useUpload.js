import { useCallback, useState } from "react";
import api from "../api";

/**
 * Multipart upload with real progress reporting.
 *
 * `progress` tracks bytes sent (0–100). After the bytes are sent the server still
 * parses and embeds the files, so `phase` switches from "uploading" to "processing".
 */
export default function useUpload() {
  const [progress, setProgress] = useState(0);
  const [phase, setPhase] = useState("idle"); // idle | uploading | processing

  const upload = useCallback(async (endpoint, formData) => {
    setProgress(0);
    setPhase("uploading");
    try {
      const res = await api.post(endpoint, formData, {
        onUploadProgress: (event) => {
          if (event.total) {
            const pct = Math.round((event.loaded / event.total) * 100);
            setProgress(pct);
            if (pct >= 100) setPhase("processing");
          }
        },
      });
      return res.data;
    } finally {
      setPhase("idle");
    }
  }, []);

  return { upload, progress, phase, busy: phase !== "idle" };
}

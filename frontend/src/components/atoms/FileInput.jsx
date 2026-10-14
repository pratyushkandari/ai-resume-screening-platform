import React from "react";

export default function FileInput({
  onChange,
  accept = ".pdf,.docx,.doc,.txt",
  label = "Click to select document",
  disabled = false,
}) {
  return (
    <label
      style={{
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        gap: 8,
        padding: "12px 16px",
        border: "1.5px dashed #cbd5e1",
        borderRadius: 8,
        textAlign: "center",
        cursor: disabled ? "not-allowed" : "pointer",
        background: "#f8fafc",
        color: "#475569",
        fontSize: 13,
        fontWeight: 600,
        transition: "all 0.15s ease",
        opacity: disabled ? 0.6 : 1,
      }}
      onMouseOver={(e) => {
        if (!disabled) e.currentTarget.style.borderColor = "#3b82f6";
      }}
      onMouseOut={(e) => {
        if (!disabled) e.currentTarget.style.borderColor = "#cbd5e1";
      }}
    >
      <input
        type="file"
        accept={accept}
        onChange={onChange}
        disabled={disabled}
        style={{ display: "none" }}
      />
      <svg
        width="16"
        height="16"
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
      >
        <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
        <polyline points="17 8 12 3 7 8" />
        <line x1="12" x2="12" y1="3" y2="15" />
      </svg>
      <span>{label}</span>
    </label>
  );
}

import React, { useState, useMemo } from "react";
import { useNavigate } from "react-router-dom";
import api from "../api";

export default function Login({ setRole }) {
  const navigate = useNavigate();
  const [isRegister, setIsRegister] = useState(false);
  const [showPassword, setShowPassword] = useState(false);
  const [form, setForm] = useState({
    name: "",
    email: "",
    password: "",
    role: "candidate"
  });

  const [msg, setMsg] = useState("");
  const [loading, setLoading] = useState(false);

  const handleChange = (e) => {
    setForm({ ...form, [e.target.name]: e.target.value });
    if (msg) setMsg("");
  };

  // Password complexity analysis
  const passwordCriteria = useMemo(() => {
    const pw = form.password;
    return {
      minLength: pw.length >= 8,
      hasUpper: /[A-Z]/.test(pw),
      hasLower: /[a-z]/.test(pw),
      hasNumber: /[0-9]/.test(pw),
      hasSpecial: /[!@#$%^&*(),.?":{}|<>\-_=+~`\[\]]/.test(pw)
    };
  }, [form.password]);

  const passwordScore = useMemo(() => {
    const { minLength, hasUpper, hasLower, hasNumber, hasSpecial } = passwordCriteria;
    return [minLength, hasUpper, hasLower, hasNumber, hasSpecial].filter(Boolean).length;
  }, [passwordCriteria]);

  const strengthConfig = useMemo(() => {
    if (!form.password) return { label: "", color: "#cbd5e1", width: "0%" };
    if (passwordScore <= 2) return { label: "Weak", color: "#ef4444", width: "33%" };
    if (passwordScore <= 4) return { label: "Medium", color: "#f59e0b", width: "66%" };
    return { label: "Strong & Secure", color: "#10b981", width: "100%" };
  }, [passwordScore, form.password]);

  const submit = async () => {
    setMsg("");

    const email = form.email.trim().toLowerCase();
    const password = form.password;

    if (!email || !password || (isRegister && !form.name.trim())) {
      setMsg("Please complete all required fields.");
      return;
    }

    const emailRegex = /^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$/;
    if (!emailRegex.test(email)) {
      setMsg("Please enter a valid email address.");
      return;
    }

    if (isRegister) {
      if (form.name.trim().length < 2) {
        setMsg("Full name must be at least 2 characters.");
        return;
      }
      if (passwordScore < 5) {
        setMsg("Password must meet all complexity requirements.");
        return;
      }
    }

    setLoading(true);

    try {
      if (isRegister) {
        const payload = {
          name: form.name.trim(),
          email: email,
          password: password,
          role: form.role
        };
        const res = await api.post("/api/register", payload);
        if (res.data?.access_token) {
          localStorage.setItem("token", res.data.access_token);
        }
        setMsg("Account registered successfully. Please sign in.");
        setIsRegister(false);
      } else {
        const payload = {
          email: email,
          password: password
        };
        const res = await api.post("/api/login", payload);
        const loggedRole = (res.data.role || "").toLowerCase().trim();

        localStorage.setItem("token", res.data.access_token);
        localStorage.setItem("role", loggedRole);
        localStorage.setItem("user_id", String(res.data.user_id));
        localStorage.setItem("name", res.data.name || "");

        setRole(loggedRole);

        if (loggedRole === "hr") {
          navigate("/");
        } else {
          navigate("/candidate");
        }
      }
    } catch (e) {
      let errorMsg = "Authentication failed. Please check your credentials.";
      if (e.response?.data?.detail) {
        if (typeof e.response.data.detail === "string") {
          errorMsg = e.response.data.detail;
        } else if (Array.isArray(e.response.data.detail)) {
          errorMsg = e.response.data.detail.map(d => d.msg || JSON.stringify(d)).join("; ");
        } else {
          errorMsg = JSON.stringify(e.response.data.detail);
        }
      } else if (e.message) {
        errorMsg = e.message;
      }
      setMsg(errorMsg);
    } finally {
      setLoading(false);
    }
  };

  const labelStyle = {
    display: "block",
    fontSize: "12px",
    fontWeight: "600",
    color: "#334155",
    marginBottom: "5px"
  };

  const inputStyle = {
    width: "100%",
    padding: "10px 12px",
    fontSize: "14px",
    borderRadius: "6px",
    border: "1px solid #cbd5e1",
    backgroundColor: "#ffffff",
    boxSizing: "border-box",
    outline: "none"
  };

  return (
    <div
      style={{
        minHeight: "100vh",
        display: "flex",
        justifyContent: "center",
        alignItems: "center",
        backgroundColor: "#0f172a",
        backgroundImage: "radial-gradient(at 0% 0%, #1e293b 0px, transparent 50%), radial-gradient(at 100% 100%, #1e3a8a 0px, transparent 50%)",
        padding: 20
      }}
    >
      <div
        style={{
          width: "100%",
          maxWidth: 420,
          padding: 32,
          borderRadius: 16,
          backgroundColor: "#ffffff",
          boxShadow: "0 20px 25px -5px rgba(0, 0, 0, 0.2), 0 8px 10px -6px rgba(0, 0, 0, 0.2)"
        }}
      >
        {/* Brand Header */}
        <div style={{ textAlign: "center", marginBottom: 24 }}>
          <div
            style={{
              width: 40,
              height: 40,
              borderRadius: 10,
              backgroundColor: "#2563eb",
              color: "#ffffff",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              margin: "0 auto 12px auto",
              boxShadow: "0 4px 12px rgba(37, 99, 235, 0.3)"
            }}
          >
            <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
              <rect width="20" height="14" x="2" y="7" rx="2" ry="2"/>
              <path d="M16 21V5a2 2 0 0 0-2-2h-4a2 2 0 0 0-2 2v16"/>
            </svg>
          </div>
          <h2 style={{ margin: "0 0 4px 0", fontWeight: "800", color: "#0f172a", fontSize: "22px", letterSpacing: "-0.02em" }}>
            {isRegister ? "Create Your Account" : "Sign In to TalentFlow"}
          </h2>
          <p style={{ fontSize: "13px", color: "#64748b", margin: 0 }}>
            {isRegister ? "Recruitment screening and candidate matching platform" : "Enter your credentials to access your workspace"}
          </p>
        </div>

        {/* Message Notice */}
        {msg && (
          <div
            style={{
              padding: "10px 14px",
              borderRadius: 6,
              fontSize: "13px",
              marginBottom: 16,
              backgroundColor: msg.includes("success") || msg.includes("registered") ? "#ecfdf5" : "#fff1f2",
              color: msg.includes("success") || msg.includes("registered") ? "#047857" : "#be123c",
              border: `1px solid ${msg.includes("success") || msg.includes("registered") ? "#a7f3d0" : "#fecdd3"}`
            }}
          >
            {msg}
          </div>
        )}

        {isRegister && (
          <div style={{ marginBottom: 14 }}>
            <label style={labelStyle}>Full Name</label>
            <input
              name="name"
              placeholder="e.g. Alex Johnson"
              value={form.name}
              onChange={handleChange}
              style={inputStyle}
            />
          </div>
        )}

        <div style={{ marginBottom: 14 }}>
          <label style={labelStyle}>Email Address</label>
          <input
            name="email"
            type="email"
            placeholder="e.g. alex@company.com"
            value={form.email}
            onChange={handleChange}
            style={inputStyle}
          />
        </div>

        <div style={{ marginBottom: 14, position: "relative" }}>
          <label style={labelStyle}>Password</label>
          <div style={{ position: "relative" }}>
            <input
              name="password"
              type={showPassword ? "text" : "password"}
              placeholder="Enter password"
              value={form.password}
              onChange={handleChange}
              onKeyDown={(e) => e.key === "Enter" && submit()}
              style={{ ...inputStyle, paddingRight: 40 }}
            />
            <button
              type="button"
              onClick={() => setShowPassword(!showPassword)}
              style={{
                position: "absolute",
                right: 10,
                top: "50%",
                transform: "translateY(-50%)",
                background: "transparent",
                border: "none",
                cursor: "pointer",
                color: "#64748b",
                display: "flex",
                alignItems: "center"
              }}
            >
              {showPassword ? (
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19m-6.72-1.07a3 3 0 1 1-4.24-4.24"/><line x1="1" y1="1" x2="23" y2="23"/></svg>
              ) : (
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/></svg>
              )}
            </button>
          </div>
        </div>

        {/* Password Strength Indicator (Registration Only) */}
        {isRegister && form.password && (
          <div style={{ marginBottom: 16 }}>
            <div style={{ display: "flex", justifyContent: "space-between", fontSize: "11px", marginBottom: 4, fontWeight: 600 }}>
              <span style={{ color: "#64748b" }}>Security Strength:</span>
              <span style={{ color: strengthConfig.color }}>{strengthConfig.label}</span>
            </div>
            <div style={{ width: "100%", height: 4, backgroundColor: "#f1f5f9", borderRadius: 2, overflow: "hidden" }}>
              <div style={{ width: strengthConfig.width, height: "100%", backgroundColor: strengthConfig.color, transition: "all 0.2s" }} />
            </div>

            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 4, marginTop: 8, fontSize: "11px" }}>
              <span style={{ color: passwordCriteria.minLength ? "#059669" : "#94a3b8" }}>
                {passwordCriteria.minLength ? "✓" : "•"} Min 8 characters
              </span>
              <span style={{ color: passwordCriteria.hasUpper ? "#059669" : "#94a3b8" }}>
                {passwordCriteria.hasUpper ? "✓" : "•"} Uppercase (A-Z)
              </span>
              <span style={{ color: passwordCriteria.hasLower ? "#059669" : "#94a3b8" }}>
                {passwordCriteria.hasLower ? "✓" : "•"} Lowercase (a-z)
              </span>
              <span style={{ color: passwordCriteria.hasNumber ? "#059669" : "#94a3b8" }}>
                {passwordCriteria.hasNumber ? "✓" : "•"} Number (0-9)
              </span>
              <span style={{ color: passwordCriteria.hasSpecial ? "#059669" : "#94a3b8", gridColumn: "span 2" }}>
                {passwordCriteria.hasSpecial ? "✓" : "•"} Special character (!@#$%...)
              </span>
            </div>
          </div>
        )}

        {/* Role Selector (Registration Only) */}
        {isRegister && (
          <div style={{ marginBottom: 18 }}>
            <label style={labelStyle}>Account Role</label>
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8 }}>
              <button
                type="button"
                onClick={() => setForm({ ...form, role: "candidate" })}
                style={{
                  padding: "8px",
                  borderRadius: "6px",
                  fontSize: "13px",
                  fontWeight: "600",
                  cursor: "pointer",
                  backgroundColor: form.role === "candidate" ? "#eff6ff" : "#f8fafc",
                  color: form.role === "candidate" ? "#1d4ed8" : "#64748b",
                  border: `1.5px solid ${form.role === "candidate" ? "#3b82f6" : "#e2e8f0"}`
                }}
              >
                Candidate
              </button>
              <button
                type="button"
                onClick={() => setForm({ ...form, role: "hr" })}
                style={{
                  padding: "8px",
                  borderRadius: "6px",
                  fontSize: "13px",
                  fontWeight: "600",
                  cursor: "pointer",
                  backgroundColor: form.role === "hr" ? "#eff6ff" : "#f8fafc",
                  color: form.role === "hr" ? "#1d4ed8" : "#64748b",
                  border: `1.5px solid ${form.role === "hr" ? "#3b82f6" : "#e2e8f0"}`
                }}
              >
                Recruiter / HR
              </button>
            </div>
          </div>
        )}

        {/* Submit Button */}
        <button
          onClick={submit}
          disabled={loading}
          className="btn btn-primary"
          style={{ width: "100%", padding: "11px", fontSize: "14px", fontWeight: 700 }}
        >
          {loading ? "Authenticating..." : isRegister ? "Create Account" : "Sign In"}
        </button>

        {/* Toggle Mode */}
        <div style={{ textAlign: "center", marginTop: 18, fontSize: "13px", color: "#64748b" }}>
          {isRegister ? "Already have an account?" : "Don't have an account yet?"}{" "}
          <button
            type="button"
            onClick={() => {
              setIsRegister(!isRegister);
              setMsg("");
            }}
            style={{
              background: "transparent",
              border: "none",
              color: "#2563eb",
              fontWeight: 700,
              cursor: "pointer",
              padding: 0
            }}
          >
            {isRegister ? "Sign In" : "Register Now"}
          </button>
        </div>
      </div>
    </div>
  );
}
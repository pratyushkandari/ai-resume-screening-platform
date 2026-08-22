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
      setMsg("⚠️ Please complete all required fields.");
      return;
    }

    const emailRegex = /^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$/;
    if (!emailRegex.test(email)) {
      setMsg("❌ Invalid email format (e.g. user@company.com).");
      return;
    }

    if (isRegister) {
      if (form.name.trim().length < 2) {
        setMsg("❌ Full name must be at least 2 characters.");
        return;
      }
      if (passwordScore < 5) {
        setMsg("❌ Please fulfill all password security criteria.");
        return;
      }
    }

    setLoading(true);

    try {
      const fd = new FormData();

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
        setMsg("✅ Account registered successfully! Please sign in.");
        setIsRegister(false);
      } else {
        const payload = {
          email: email,
          password: password
        };
        const res = await api.post("/api/login", payload);
        const loggedRole = (res.data.role || "").toLowerCase().trim();
        const userId = res.data.user_id;
        const token = res.data.access_token;

        if (!userId || !loggedRole) {
          setMsg("❌ Invalid session response received from server.");
          setLoading(false);
          return;
        }

        // Store JWT Bearer token & user profile
        if (token) {
          localStorage.setItem("token", token);
        }
        localStorage.setItem("role", loggedRole);
        localStorage.setItem("name", res.data.name || "User");
        localStorage.setItem("user_id", String(userId));

        setRole(loggedRole);
        navigate(loggedRole === "hr" ? "/" : "/candidate");
      }
    } catch (e) {
      let errorMsg = "Authentication failed. Please verify credentials.";
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
      setMsg("❌ " + errorMsg);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div
      style={{
        minHeight: "100vh",
        display: "flex",
        justifyContent: "center",
        alignItems: "center",
        background: "linear-gradient(135deg, #0f172a 0%, #1e3a8a 50%, #312e81 100%)",
        padding: 20
      }}
    >
      <div
        style={{
          width: "100%",
          maxWidth: 420,
          padding: 32,
          borderRadius: 20,
          background: "rgba(255,255,255,0.98)",
          boxShadow: "0 25px 60px rgba(0,0,0,0.3)",
          backdropFilter: "blur(16px)"
        }}
      >
        <div style={{ textAlign: "center", marginBottom: 20 }}>
          <div style={{ fontSize: 38 }}>⚡</div>
          <h2 style={{ margin: "6px 0", fontWeight: "800", color: "#0f172a", fontSize: "24px" }}>
            {isRegister ? "Create Your Account" : "Enterprise Portal Sign In"}
          </h2>
          <p style={{ fontSize: "13px", color: "#64748b", margin: 0 }}>
            {isRegister ? "Join the high-speed recruitment & screening engine" : "Access your AI-ranked candidates & job matches"}
          </p>
        </div>

        {isRegister && (
          <div style={{ marginBottom: 12 }}>
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

        <div style={{ marginBottom: 12 }}>
          <label style={labelStyle}>Work / Professional Email</label>
          <input
            name="email"
            type="email"
            placeholder="e.g. alex@company.com"
            value={form.email}
            onChange={handleChange}
            style={inputStyle}
          />
        </div>

        <div style={{ marginBottom: 12, position: "relative" }}>
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
                fontSize: 16,
                color: "#64748b"
              }}
            >
              {showPassword ? "🙈" : "👁️"}
            </button>
          </div>

          {/* Interactive Password Strength Meter for Registration */}
          {isRegister && form.password && (
            <div style={{ marginTop: 8 }}>
              <div style={{ display: "flex", justifyContent: "space-between", fontSize: 11, fontWeight: 700, color: strengthConfig.color, marginBottom: 4 }}>
                <span>Security Level</span>
                <span>{strengthConfig.label}</span>
              </div>
              <div style={{ width: "100%", height: 5, background: "#e2e8f0", borderRadius: 4, overflow: "hidden" }}>
                <div style={{ width: strengthConfig.width, height: "100%", background: strengthConfig.color, transition: "all 0.3s ease" }} />
              </div>

              {/* Requirement Checkpoints */}
              <div style={{ marginTop: 8, display: "grid", gridTemplateColumns: "1fr 1fr", gap: 4, fontSize: 11 }}>
                <span style={{ color: passwordCriteria.minLength ? "#10b981" : "#94a3b8" }}>
                  {passwordCriteria.minLength ? "✓" : "○"} 8+ Characters
                </span>
                <span style={{ color: passwordCriteria.hasUpper ? "#10b981" : "#94a3b8" }}>
                  {passwordCriteria.hasUpper ? "✓" : "○"} Uppercase (A-Z)
                </span>
                <span style={{ color: passwordCriteria.hasLower ? "#10b981" : "#94a3b8" }}>
                  {passwordCriteria.hasLower ? "✓" : "○"} Lowercase (a-z)
                </span>
                <span style={{ color: passwordCriteria.hasNumber ? "#10b981" : "#94a3b8" }}>
                  {passwordCriteria.hasNumber ? "✓" : "○"} Numeric Digit (0-9)
                </span>
                <span style={{ color: passwordCriteria.hasSpecial ? "#10b981" : "#94a3b8", gridColumn: "span 2" }}>
                  {passwordCriteria.hasSpecial ? "✓" : "○"} Special Character (!@#$...)
                </span>
              </div>
            </div>
          )}
        </div>

        {isRegister && (
          <div style={{ marginBottom: 12 }}>
            <label style={labelStyle}>Portal Account Type</label>
            <select
              name="role"
              value={form.role}
              onChange={handleChange}
              style={inputStyle}
            >
              <option value="candidate">Candidate (Job Seeker / Resume Submissions)</option>
              <option value="hr">HR / Recruiter (Post Jobs & AI Screening)</option>
            </select>
          </div>
        )}

        <button
          onClick={submit}
          disabled={loading}
          style={{
            marginTop: 18,
            width: "100%",
            padding: "13px",
            background: loading ? "#94a3b8" : "linear-gradient(135deg, #2563eb 0%, #1d4ed8 100%)",
            color: "#fff",
            border: "none",
            borderRadius: 10,
            fontWeight: "700",
            fontSize: "14px",
            cursor: loading ? "not-allowed" : "pointer",
            boxShadow: "0 4px 14px rgba(37,99,235,0.3)",
            transition: "all 0.2s"
          }}
        >
          {loading ? "Authenticating..." : isRegister ? "Create Secure Account" : "Sign In to Platform"}
        </button>

        {msg && (
          <div
            style={{
              marginTop: 16,
              fontSize: 13,
              textAlign: "center",
              padding: "10px",
              borderRadius: "8px",
              background: msg.includes("❌") || msg.includes("⚠️") ? "#fee2e2" : "#dcfce7",
              color: msg.includes("❌") || msg.includes("⚠️") ? "#dc2626" : "#16a34a",
              fontWeight: "600",
              border: `1px solid ${msg.includes("❌") || msg.includes("⚠️") ? "#fca5a5" : "#86efac"}`
            }}
          >
            {msg}
          </div>
        )}

        <div
          style={{
            marginTop: 22,
            textAlign: "center",
            cursor: "pointer",
            color: "#2563eb",
            fontWeight: 700,
            fontSize: "13px"
          }}
          onClick={() => {
            setMsg("");
            setIsRegister(!isRegister);
          }}
        >
          {isRegister ? "Already registered? Sign In" : "Need an account? Register Here"}
        </div>
      </div>
    </div>
  );
}

const labelStyle = {
  display: "block",
  fontSize: "12px",
  fontWeight: "700",
  color: "#334155",
  marginBottom: "4px"
};

const inputStyle = {
  width: "100%",
  padding: "10px 12px",
  borderRadius: 8,
  border: "1px solid #cbd5e1",
  outline: "none",
  fontSize: 14,
  boxSizing: "border-box",
  color: "#0f172a",
  background: "#f8fafc",
  transition: "border 0.2s"
};
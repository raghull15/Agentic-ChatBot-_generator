import React, { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import { Eye, EyeOff, Sparkles, ArrowRight, Gift } from "lucide-react";

export default function Register() {
  const [formData, setFormData] = useState({
    name: "",
    phone: "",
    email: "",
    password: "",
    confirmPassword: "",
  });
  const [showPassword, setShowPassword] = useState(false);
  const [showConfirmPassword, setShowConfirmPassword] = useState(false);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const navigate = useNavigate();
  const { register } = useAuth();

  const handleChange = (e) => {
    setFormData({ ...formData, [e.target.name]: e.target.value });
    if (error) setError("");
  };

  const handleRegister = async (e) => {
    e.preventDefault();
    const { name, phone, email, password, confirmPassword } = formData;

    if (!name || !phone || !email || !password || !confirmPassword) {
      setError("Please fill in all fields");
      return;
    }

    if (password !== confirmPassword) {
      setError("Passwords do not match");
      return;
    }

    if (password.length < 6) {
      setError("Password must be at least 6 characters");
      return;
    }

    try {
      setLoading(true);
      setError("");
      await register(name, email, phone, password);
      navigate("/home");
    } catch (err) {
      setError(err.message || "Registration failed");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-[var(--bg-primary)] flex">
      {/* Left Side - Form */}
      <div className="w-full lg:w-1/2 flex items-center justify-center p-6 sm:p-12">
        <div className="w-full max-w-md animate-fadeIn">
          {/* Header */}
          <div className="mb-8">
            <div className="flex items-center gap-3 mb-6">
              <div className="w-12 h-12 bg-gradient-to-br from-[var(--primary)] to-[var(--primary-hover)] rounded-xl flex items-center justify-center">
                <Sparkles className="w-6 h-6 text-white" />
              </div>
              <h1 className="text-3xl font-bold text-[var(--text-primary)]">
                Create Account
              </h1>
            </div>
            <p className="text-[var(--text-muted)]">
              Get started with your AI agents today
            </p>

            {/* Free Credits Badge */}
            <div className="mt-4 inline-flex items-center gap-2 px-4 py-2 bg-gradient-to-r from-[var(--secondary)]/10 to-[var(--secondary)]/5 border border-[var(--secondary)] rounded-lg">
              <Gift className="w-5 h-5 text-[var(--secondary)]" />
              <span className="text-sm font-semibold text-[var(--secondary)]">
                Get 10 free credits on signup!
              </span>
            </div>
          </div>

          {/* Error Alert */}
          {error && (
            <div className="alert alert-error mb-6">
              <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
              {error}
            </div>
          )}

          {/* Form */}
          <form onSubmit={handleRegister} className="space-y-5">
            <div>
              <label className="block text-xs font-semibold uppercase tracking-wider text-[var(--text-muted)] mb-2">
                Full Name
              </label>
              <input
                name="name"
                type="text"
                className="input"
                placeholder="John Doe"
                value={formData.name}
                onChange={handleChange}
                disabled={loading}
              />
            </div>

            <div>
              <label className="block text-xs font-semibold uppercase tracking-wider text-[var(--text-muted)] mb-2">
                Phone Number
              </label>
              <input
                name="phone"
                type="tel"
                className="input"
                placeholder="+1 (555) 000-0000"
                value={formData.phone}
                onChange={handleChange}
                disabled={loading}
              />
            </div>

            <div>
              <label className="block text-xs font-semibold uppercase tracking-wider text-[var(--text-muted)] mb-2">
                Email Address
              </label>
              <input
                name="email"
                type="email"
                className="input"
                placeholder="you@example.com"
                value={formData.email}
                onChange={handleChange}
                disabled={loading}
              />
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div>
                <label className="block text-xs font-semibold uppercase tracking-wider text-[var(--text-muted)] mb-2">
                  Password
                </label>
                <div className="input-with-icon">
                  <input
                    name="password"
                    type={showPassword ? "text" : "password"}
                    className="input"
                    placeholder="Min 6 characters"
                    value={formData.password}
                    onChange={handleChange}
                    disabled={loading}
                  />
                  <div
                    className="input-icon"
                    onClick={() => setShowPassword(!showPassword)}
                  >
                    {showPassword ? (
                      <EyeOff className="w-5 h-5" />
                    ) : (
                      <Eye className="w-5 h-5" />
                    )}
                  </div>
                </div>
              </div>

              <div>
                <label className="block text-xs font-semibold uppercase tracking-wider text-[var(--text-muted)] mb-2">
                  Confirm Password
                </label>
                <div className="input-with-icon">
                  <input
                    name="confirmPassword"
                    type={showConfirmPassword ? "text" : "password"}
                    className="input"
                    placeholder="Confirm password"
                    value={formData.confirmPassword}
                    onChange={handleChange}
                    disabled={loading}
                  />
                  <div
                    className="input-icon"
                    onClick={() => setShowConfirmPassword(!showConfirmPassword)}
                  >
                    {showConfirmPassword ? (
                      <EyeOff className="w-5 h-5" />
                    ) : (
                      <Eye className="w-5 h-5" />
                    )}
                  </div>
                </div>
              </div>
            </div>

            <button
              type="submit"
              className="btn btn-primary w-full mt-6"
              disabled={loading}
            >
              {loading ? (
                <>
                  <div className="animate-spin w-5 h-5 border-2 border-white border-t-transparent rounded-full" />
                  Creating account...
                </>
              ) : (
                <>
                  Create Account
                  <ArrowRight className="w-5 h-5" />
                </>
              )}
            </button>
          </form>

          {/* Divider */}
          <div className="relative my-8">
            <div className="absolute inset-0 flex items-center">
              <div className="w-full border-t border-[var(--border-color)]"></div>
            </div>
            <div className="relative flex justify-center text-sm">
              <span className="px-4 bg-[var(--bg-primary)] text-[var(--text-muted)]">
                Already have an account?
              </span>
            </div>
          </div>

          {/* Login Link */}
          <button
            onClick={() => navigate("/login")}
            className="btn btn-secondary w-full"
          >
            Sign In
          </button>
        </div>
      </div>

      {/* Right Side - Illustration/Testimonial */}
      <div className="hidden lg:flex lg:w-1/2 bg-gradient-to-br from-[var(--secondary)] to-[var(--secondary-hover)] items-center justify-center p-12 relative overflow-hidden">
        {/* Gradient Orb */}
        <div className="gradient-orb" style={{ top: '-200px', right: '-200px', background: 'radial-gradient(circle, rgba(16, 185, 129, 0.3), transparent 70%)' }} />

        <div className="relative z-10 text-white max-w-lg">
          <h2 className="text-4xl font-bold mb-6">
            Start Building Today
          </h2>
          <p className="text-lg text-white/90 mb-8">
            Join thousands of developers creating intelligent AI agents. No credit card required to get started.
          </p>

          {/* Stats */}
          <div className="grid grid-cols-3 gap-6 mb-8">
            {[
              { label: "Active Users", value: "10K+" },
              { label: "AI Agents", value: "50K+" },
              { label: "Queries/Day", value: "1M+" }
            ].map((stat, idx) => (
              <div key={idx} className="text-center animate-fadeIn" style={{ animationDelay: `${idx * 0.1}s` }}>
                <div className="text-3xl font-bold mb-1">{stat.value}</div>
                <div className="text-sm text-white/70">{stat.label}</div>
              </div>
            ))}
          </div>

          {/* Testimonial */}
          <div className="bg-white/10 backdrop-blur-sm border border-white/20 rounded-2xl p-6">
            <div className="flex items-center gap-1 mb-3">
              {[...Array(5)].map((_, i) => (
                <svg key={i} className="w-5 h-5 text-yellow-400" fill="currentColor" viewBox="0 0 20 20">
                  <path d="M9.049 2.927c.3-.921 1.603-.921 1.902 0l1.07 3.292a1 1 0 00.95.69h3.462c.969 0 1.371 1.24.588 1.81l-2.8 2.034a1 1 0 00-.364 1.118l1.07 3.292c.3.921-.755 1.688-1.54 1.118l-2.8-2.034a1 1 0 00-1.175 0l-2.8 2.034c-.784.57-1.838-.197-1.539-1.118l1.07-3.292a1 1 0 00-.364-1.118L2.98 8.72c-.783-.57-.38-1.81.588-1.81h3.461a1 1 0 00.951-.69l1.07-3.292z" />
                </svg>
              ))}
            </div>
            <p className="text-white/90 mb-3">
              "This platform transformed how we handle customer support. Our AI agent handles 80% of queries automatically!"
            </p>
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 bg-white/20 rounded-full" />
              <div>
                <div className="font-semibold">Sarah Johnson</div>
                <div className="text-sm text-white/70">CEO, TechStart</div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

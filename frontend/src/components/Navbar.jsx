import React, { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import { useTheme } from "../context/ThemeContext";
import { Menu, X, Sun, Moon, Plus, Bot } from "lucide-react";
import CreditBalance from "./CreditBalance";

export default function Navbar() {
  const navigate = useNavigate();
  const { user, logout } = useAuth();
  const { isDark, toggleTheme } = useTheme();
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);

  const handleLogout = () => {
    logout();
    navigate("/");
  };

  return (
    <nav className="bg-[var(--bg-secondary)] border-b border-[var(--border-color)] sticky top-0 z-50 backdrop-blur-sm">
      <div className="max-w-7xl mx-auto px-4 sm:px-6">
        <div className="flex justify-between items-center h-16">
          {/* Logo */}
          <div
            className="cursor-pointer flex items-center gap-2 group"
            onClick={() => navigate("/home")}
          >
            <div className="w-10 h-10 bg-gradient-to-br from-[var(--primary)] to-[var(--primary-hover)] rounded-xl flex items-center justify-center shadow-lg group-hover:scale-110 transition-transform glow-primary">
              <Bot className="w-6 h-6 text-white" />
            </div>
            <span className="text-2xl font-bold tracking-tighter text-[var(--text-primary)]">
              Agentic<span className="text-gradient">Loop</span>
            </span>
          </div>
          {/* Desktop Navigation */}
          <div className="hidden md:flex items-center gap-2">
            {user && (
              <span className="text-xs text-[var(--text-muted)] mr-4 hidden lg:inline">
                {user.email}
              </span>
            )}

            <CreditBalance />

            <button
              onClick={() => navigate("/home")}
              className="btn btn-secondary btn-sm"
            >
              Dashboard
            </button>

            {/* Admin Link - only for admins */}
            {user?.isAdmin && (
              <button
                onClick={() => navigate("/admin")}
                className="btn btn-secondary btn-sm"
              >
                Admin
              </button>
            )}

            <button
              onClick={() => navigate("/create-agent")}
              className="btn btn-primary btn-sm"
            >
              <Plus className="w-4 h-4" />
              <span className="hidden lg:inline">New Agent</span>
            </button>

            {/* Theme Toggle */}
            <button
              onClick={toggleTheme}
              className="p-2 text-[var(--text-muted)] hover:text-[var(--text-primary)] transition-colors"
              title={isDark ? 'Switch to Light Mode' : 'Switch to Dark Mode'}
            >
              {isDark ? <Sun className="w-5 h-5" /> : <Moon className="w-5 h-5" />}
            </button>

            <button
              onClick={handleLogout}
              className="btn btn-secondary btn-sm"
            >
              Logout
            </button>
          </div>

          {/* Mobile Menu Button */}
          <button
            className="md:hidden p-2 text-[var(--text-secondary)] hover:text-[var(--text-primary)]"
            onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
          >
            {mobileMenuOpen ? <X className="w-6 h-6" /> : <Menu className="w-6 h-6" />}
          </button>
        </div>

        {/* Mobile Menu */}
        {mobileMenuOpen && (
          <div className="md:hidden border-t border-[var(--border-color)] py-4 space-y-2">
            {user && (
              <p className="px-2 py-2 text-xs text-[var(--text-muted)]">
                {user.email}
              </p>
            )}

            <div className="px-2 mb-4">
              <CreditBalance />
            </div>

            <button
              onClick={() => { navigate("/home"); setMobileMenuOpen(false); }}
              className="w-full text-left px-2 py-3 text-sm font-semibold text-[var(--text-primary)] hover:bg-[var(--bg-tertiary)] rounded-lg transition-colors"
            >
              Dashboard
            </button>

            {user?.isAdmin && (
              <button
                onClick={() => { navigate("/admin"); setMobileMenuOpen(false); }}
                className="w-full text-left px-2 py-3 text-sm font-semibold text-[var(--text-primary)] hover:bg-[var(--bg-tertiary)] rounded-lg transition-colors"
              >
                Admin
              </button>
            )}

            <button
              onClick={() => { navigate("/create-agent"); setMobileMenuOpen(false); }}
              className="w-full text-left px-2 py-3 text-sm font-semibold text-[var(--primary)] hover:bg-[var(--bg-tertiary)] rounded-lg transition-colors"
            >
              + New Agent
            </button>

            <button
              onClick={() => { navigate("/billing"); setMobileMenuOpen(false); }}
              className="w-full text-left px-2 py-3 text-sm font-semibold text-[var(--text-primary)] hover:bg-[var(--bg-tertiary)] rounded-lg transition-colors"
            >
              Billing
            </button>

            <button
              onClick={toggleTheme}
              className="w-full text-left px-2 py-3 text-sm font-semibold text-[var(--text-primary)] hover:bg-[var(--bg-tertiary)] rounded-lg transition-colors flex items-center gap-2"
            >
              {isDark ? <Sun className="w-4 h-4" /> : <Moon className="w-4 h-4" />}
              {isDark ? 'Light Mode' : 'Dark Mode'}
            </button>

            <button
              onClick={() => { handleLogout(); setMobileMenuOpen(false); }}
              className="w-full text-left px-2 py-3 text-sm font-semibold text-[var(--danger)] hover:bg-[var(--bg-tertiary)] rounded-lg transition-colors"
            >
              Logout
            </button>
          </div>
        )}
      </div>
    </nav>
  );
}

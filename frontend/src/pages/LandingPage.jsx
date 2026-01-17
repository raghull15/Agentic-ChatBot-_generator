import React from "react";
import { useNavigate } from "react-router-dom";
import { Bot, Zap, Shield, ArrowRight, Sparkles, Database, Globe, Lock } from "lucide-react";
import { useTheme } from "../context/ThemeContext";

export default function LandingPage() {
    const navigate = useNavigate();
    const { isDark } = useTheme();

    return (
        <div className="min-h-screen bg-[var(--bg-primary)] relative overflow-hidden">
            {/* Grid Pattern Background */}
            <div className="absolute inset-0 grid-pattern opacity-50" />

            {/* Gradient Orb - Light Mode */}
            <div className="hidden dark:hidden gradient-orb" style={{ top: '10%', right: '10%' }} />

            {/* Gradient Orb - Dark Mode */}
            <div className="hidden dark:block gradient-orb" style={{ top: '10%', right: '10%' }} />

            {/* Hero Section */}
            <div className="relative z-10 max-w-7xl mx-auto px-4 py-16 sm:py-24">
                <div className="text-center animate-fadeIn">
                    {/* Logo icon */}
                    <div className="inline-flex items-center justify-center w-20 h-20 bg-gradient-to-br from-[var(--primary)] to-[var(--primary-hover)] rounded-2xl mb-8 shadow-lg glow-primary">
                        <Bot className="w-10 h-10 text-white" />
                    </div>

                    {/* Headline */}
                    <h1 className="text-5xl sm:text-7xl font-bold tracking-tight text-[var(--text-primary)] mb-6">
                        Build Your{" "}
                        <span className="text-gradient">AI Chatbot</span>
                    </h1>
                    <p className="text-xl sm:text-2xl text-[var(--text-secondary)] mb-12 max-w-3xl mx-auto leading-relaxed">
                        Create intelligent chatbots powered by your documents.
                        Upload PDFs, CSVs, or connect databases — get answers instantly with{" "}
                        <span className="font-semibold text-[var(--primary)]">RAG technology</span>.
                    </p>

                    {/* CTA Buttons */}
                    <div className="flex flex-col sm:flex-row gap-4 justify-center items-center mb-16">
                        <button
                            onClick={() => navigate("/register")}
                            className="btn btn-primary text-lg px-10 py-5 shadow-xl"
                        >
                            <Sparkles className="w-6 h-6" />
                            Get Started Free
                            <ArrowRight className="w-6 h-6" />
                        </button>
                        <button
                            onClick={() => navigate("/login")}
                            className="btn btn-secondary text-lg px-10 py-5"
                        >
                            Sign In
                        </button>
                    </div>

                    {/* Trust Badge */}
                    <div className="flex items-center justify-center gap-2 text-sm text-[var(--text-muted)]">
                        <Shield className="w-4 h-4 text-[var(--secondary)]" />
                        <span>No credit card required • 10 free credits on signup</span>
                    </div>
                </div>

                {/* Features Grid - Glassmorphism */}
                <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mt-24">
                    <FeatureCard
                        icon={<Database className="w-7 h-7" />}
                        title="Multiple Data Sources"
                        description="PDF, CSV, Word docs, SQL databases, MongoDB — use any data to train your bot"
                        delay="0.1s"
                        color="primary"
                    />
                    <FeatureCard
                        icon={<Zap className="w-7 h-7" />}
                        title="Instant Responses"
                        description="Get intelligent answers from your documents in real-time with streaming"
                        delay="0.2s"
                        color="secondary"
                    />
                    <FeatureCard
                        icon={<Globe className="w-7 h-7" />}
                        title="Embeddable Widgets"
                        description="Deploy your chatbot anywhere with a simple script tag. Fully customizable."
                        delay="0.3s"
                        color="accent"
                    />
                </div>

                {/* Stats Section */}
                <div className="grid grid-cols-2 md:grid-cols-4 gap-8 mt-24 p-8 bg-[var(--bg-secondary)] border border-[var(--border-color)] rounded-2xl">
                    <StatCard number="10K+" label="Active Users" />
                    <StatCard number="50K+" label="AI Agents" />
                    <StatCard number="1M+" label="Queries/Day" />
                    <StatCard number="99.9%" label="Uptime" />
                </div>

                {/* How It Works */}
                <div className="mt-32">
                    <h2 className="text-4xl font-bold text-center text-[var(--text-primary)] mb-16">
                        How It Works
                    </h2>
                    <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
                        <StepCard
                            number="1"
                            title="Upload Your Data"
                            description="Upload PDFs, CSVs, or connect your database. We support multiple data sources."
                        />
                        <StepCard
                            number="2"
                            title="Train Your Agent"
                            description="Our AI processes your documents and creates a knowledge base automatically."
                        />
                        <StepCard
                            number="3"
                            title="Deploy Anywhere"
                            description="Embed on your website, integrate via API, or use our dashboard to chat."
                        />
                    </div>
                </div>
            </div>

            {/* Footer */}
            <div className="relative z-10 border-t border-[var(--border-color)] py-8 mt-24">
                <p className="text-center text-sm text-[var(--text-muted)]">
                    © 2024 Agentic AI. Built with ❤️ using React, Flask, LangChain, and Ollama.
                </p>
            </div>
        </div>
    );
}

function FeatureCard({ icon, title, description, delay, color }) {
    const colorMap = {
        primary: '#7C3AED',    // Violet
        secondary: '#10B981',  // Emerald
        accent: '#2563EB'      // Blue
    };

    return (
        <div
            className="card card-glass p-8 text-center animate-fadeIn hover:scale-105"
            style={{ animationDelay: delay }}
        >
            <div
                className="w-16 h-16 mx-auto mb-6 rounded-2xl flex items-center justify-center shadow-lg"
                style={{
                    background: `linear-gradient(135deg, ${colorMap[color]}, ${colorMap[color]}dd)`,
                    boxShadow: `0 8px 24px ${colorMap[color]}40`
                }}
            >
                <div style={{ color: '#FFFFFF' }}>
                    {icon}
                </div>
            </div>
            <h3 className="text-xl font-bold text-[var(--text-primary)] mb-3">
                {title}
            </h3>
            <p className="text-[var(--text-muted)] leading-relaxed">
                {description}
            </p>
        </div>
    );
}

function StatCard({ number, label }) {
    return (
        <div className="text-center">
            <div className="text-4xl font-bold text-gradient mb-2">
                {number}
            </div>
            <div className="text-sm text-[var(--text-muted)] uppercase tracking-wider">
                {label}
            </div>
        </div>
    );
}

function StepCard({ number, title, description }) {
    return (
        <div className="relative">
            <div className="flex items-start gap-4">
                <div className="flex-shrink-0 w-12 h-12 bg-gradient-to-br from-[var(--primary)] to-[var(--primary-hover)] rounded-xl flex items-center justify-center text-white font-bold text-xl shadow-lg">
                    {number}
                </div>
                <div>
                    <h3 className="text-xl font-bold text-[var(--text-primary)] mb-2">
                        {title}
                    </h3>
                    <p className="text-[var(--text-muted)] leading-relaxed">
                        {description}
                    </p>
                </div>
            </div>
        </div>
    );
}

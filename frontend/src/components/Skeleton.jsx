import React from "react";

export function Skeleton({ className = "", variant = "text" }) {
    const variants = {
        text: "h-4 w-full",
        title: "h-5 w-3/4",
        avatar: "h-12 w-12",
        card: "h-32 w-full",
        button: "h-10 w-24",
    };

    const variantClass = variants[variant] || variants.text;

    return (
        <div
            className={`bg-[var(--bg-tertiary)] animate-pulse ${variantClass} ${className}`}
        />
    );
}

export function AgentCardSkeleton() {
    return (
        <div className="bg-[var(--bg-primary)] border border-[var(--border-color)] p-4 sm:p-6">
            <div className="mb-3 sm:mb-4">
                <div className="h-5 w-3/5 bg-[var(--bg-tertiary)] mb-2 animate-pulse" />
                <div className="h-3 w-1/4 bg-[var(--bg-tertiary)] animate-pulse" />
            </div>
            <div className="h-3.5 w-full bg-[var(--bg-tertiary)] mb-2 animate-pulse" />
            <div className="h-3.5 w-2/3 bg-[var(--bg-tertiary)] mb-4 sm:mb-5 animate-pulse" />
            <div className="flex gap-3 sm:gap-4 mb-4 sm:mb-5 pb-4 sm:pb-5 border-b border-[var(--border-light)]">
                <div className="h-3 w-14 bg-[var(--bg-tertiary)] animate-pulse" />
                <div className="h-3 w-10 bg-[var(--bg-tertiary)] animate-pulse" />
            </div>
            <div className="flex justify-between">
                <div className="flex gap-2">
                    <div className="h-6 w-14 bg-[var(--bg-tertiary)] animate-pulse" />
                    <div className="h-6 w-14 bg-[var(--bg-tertiary)] animate-pulse" />
                </div>
                <div className="h-4 w-12 bg-[var(--bg-tertiary)] animate-pulse" />
            </div>
        </div>
    );
}

export function ChatMessageSkeleton() {
    return (
        <div className="flex justify-start">
            <div className="max-w-[85%] sm:max-w-[75%] md:max-w-[70%] bg-[var(--bg-secondary)] border border-[var(--border-color)] p-4">
                <div className="h-3.5 w-48 bg-[var(--bg-tertiary)] mb-2 animate-pulse" />
                <div className="h-3.5 w-64 bg-[var(--bg-tertiary)] mb-2 animate-pulse" />
                <div className="h-3.5 w-32 bg-[var(--bg-tertiary)] animate-pulse" />
            </div>
        </div>
    );
}

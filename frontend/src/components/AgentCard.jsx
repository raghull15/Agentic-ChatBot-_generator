import React, { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAgent } from "../context/AgentContext";
import EmbedModal from "./EmbedModal";
import { MessageSquare, Edit, Code, Trash2 } from "lucide-react";

export default function AgentCard({ agent }) {
  const navigate = useNavigate();
  const { removeAgent } = useAgent();
  const [showEmbed, setShowEmbed] = useState(false);
  const [isDeleting, setIsDeleting] = useState(false);

  // Determine if agent is "active" (has been used recently)
  // For now, we'll consider all agents as active
  const isActive = true;

  const handleDelete = async (e) => {
    e.stopPropagation();
    if (isDeleting) return;

    if (window.confirm(`Delete "${agent.name}"? This action cannot be undone.`)) {
      try {
        setIsDeleting(true);
        console.log(`[AgentCard] Deleting agent: ${agent.name}`);
        await removeAgent(agent.name);
        console.log(`[AgentCard] Successfully deleted: ${agent.name}`);
      } catch (err) {
        console.error(`[AgentCard] Delete failed:`, err);
        alert(`Failed to delete agent: ${err.message}`);
        setIsDeleting(false);
      }
    }
  };

  const handleEmbed = (e) => {
    e.stopPropagation();
    setShowEmbed(true);
  };

  const handleUpdate = (e) => {
    e.stopPropagation();
    navigate(`/update-agent/${agent.id}`);
  };

  return (
    <>
      <div
        onClick={() => navigate(`/chat/${agent.id}`)}
        className="card cursor-pointer group"
      >
        {/* Header with Status Dot */}
        <div className="flex items-start justify-between mb-4">
          <div className="flex items-start gap-3 min-w-0 flex-1">
            {/* Status Dot */}
            <div className={`mt-1.5 ${isActive ? 'status-dot status-dot-active' : 'status-dot status-dot-idle'}`} />

            <div className="min-w-0 flex-1">
              <h3 className="text-lg font-bold text-[var(--text-primary)] mb-1 truncate">
                {agent.name}
              </h3>
              <div className="flex items-center gap-2 flex-wrap">
                <span className="badge badge-primary text-[10px]">
                  {agent.domain || "General"}
                </span>
                {agent.embed_token && (
                  <span className="badge badge-secondary text-[10px]">
                    Embedded
                  </span>
                )}
              </div>
            </div>
          </div>
        </div>

        {/* Description */}
        <p className="text-sm text-[var(--text-muted)] mb-4 line-clamp-2 min-h-[40px]">
          {agent.description || "No description provided"}
        </p>

        {/* Meta Info */}
        <div className="flex items-center gap-4 mb-4 pb-4 border-b border-[var(--border-color)]">
          <div className="flex items-center gap-2">
            <svg className="w-4 h-4 text-[var(--text-muted)]" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
            </svg>
            <span className="text-xs text-[var(--text-muted)]">
              {agent.num_documents || 0} chunks
            </span>
          </div>
          <div className="flex items-center gap-2">
            <svg className="w-4 h-4 text-[var(--text-muted)]" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 21a4 4 0 01-4-4V5a2 2 0 012-2h4a2 2 0 012 2v12a4 4 0 01-4 4zm0 0h12a2 2 0 002-2v-4a2 2 0 00-2-2h-2.343M11 7.343l1.657-1.657a2 2 0 012.828 0l2.829 2.829a2 2 0 010 2.828l-8.486 8.485M7 17h.01" />
            </svg>
            <span className="text-xs text-[var(--text-muted)] uppercase">
              {(agent.source_type || 'pdf')}
            </span>
          </div>
        </div>

        {/* Actions */}
        <div className="flex items-center justify-between gap-2">
          <div className="flex items-center gap-1">
            <button
              onClick={handleUpdate}
              className="p-2 text-[var(--text-muted)] hover:text-[var(--primary)] hover:bg-[var(--bg-secondary)] rounded-lg transition-all"
              title="Update Agent"
            >
              <Edit className="w-4 h-4" />
            </button>
            <button
              onClick={handleEmbed}
              className="p-2 text-[var(--text-muted)] hover:text-[var(--accent)] hover:bg-[var(--bg-secondary)] rounded-lg transition-all"
              title="Get Embed Code"
            >
              <Code className="w-4 h-4" />
            </button>
            <button
              onClick={handleDelete}
              disabled={isDeleting}
              className="p-2 text-[var(--text-muted)] hover:text-[var(--danger)] hover:bg-[var(--bg-secondary)] rounded-lg transition-all disabled:opacity-50"
              title="Delete Agent"
            >
              <Trash2 className="w-4 h-4" />
            </button>
          </div>

          <div className="flex items-center gap-2 text-[var(--primary)] font-semibold text-sm group-hover:gap-3 transition-all">
            <MessageSquare className="w-4 h-4" />
            <span>Chat</span>
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
            </svg>
          </div>
        </div>
      </div>

      {showEmbed && (
        <EmbedModal agent={agent} onClose={() => setShowEmbed(false)} />
      )}
    </>
  );
}
